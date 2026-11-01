#!/usr/bin/python3
"""Expose the managed DinD phone through the SDK emulator/avdmanager interface."""
import fcntl
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time

HOME = Path.home()
ROOT = HOME / 'Projects/.agent-hub/android'
SDK = ROOT / 'sdk'
STATE = ROOT / 'user'
AVD = 'AgentHub_Pixel_Android_11'
CONTAINER = 'agent-hub-android'
HELPER = '/usr/local/bin/agent-hub-android'


def parse_launch(args):
    name, port = None, 5554
    harmless = {'-no-audio', '-no-window', '-no-boot-anim', '-no-snapshot', '-no-snapshot-load', '-no-snapshot-save', '-no-metrics'}
    values = {'-avd', '-port', '-ports', '-gpu', '-camera-back', '-camera-front'}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith('@'):
            name = arg[1:]
        elif arg in harmless:
            pass
        elif arg in values:
            i += 1
            if i == len(args):
                raise ValueError(f'Missing value for {arg}')
            value = args[i]
            if arg == '-avd':
                name = value
            elif arg in ('-port', '-ports'):
                ports = list(map(int, value.split(',')))
                port = ports[0]
                if arg == '-ports' and ports != [port, port + 1]:
                    raise ValueError('Console/ADB ports must be consecutive')
            elif arg.startswith('-camera') and value not in ('none', 'emulated') and not value.replace('\\:', ':').startswith('imagefile:'):
                raise ValueError('Host cameras and imagefile feeds are unavailable in the DinD phone')
            elif arg == '-gpu' and value not in ('auto', 'swiftshader', 'swiftshader_indirect', 'software'):
                raise ValueError('The DinD phone requires software rendering')
        else:
            raise ValueError(f'Unsupported managed-phone launch option: {arg}')
        i += 1
    if name != AVD:
        raise ValueError(f'Only the managed AVD {AVD} can be launched')
    if port < 5554 or port > 5682 or port % 2:
        raise ValueError('Console port must be even, from 5554 through 5682')
    return port


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, **kwargs)


def launch(port, args):
    if not (STATE / f'avd/{AVD}.avd/config.ini').exists():
        raise RuntimeError('Run agent-hub-android setup first')
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        info = subprocess.run(['docker', 'inspect', '--format', '{{json .State.Running}}', CONTAINER], capture_output=True, text=True)
        running = info.returncode == 0 and json.loads(info.stdout)
        port_file = ROOT / 'console-port'
        old_port = int(port_file.read_text()) if port_file.exists() else 5554
        if running and old_port != port:
            raise RuntimeError(f'The managed phone is already running as emulator-{old_port}')
        if not running:
            # Refuse collisions with unrelated local devices/services.
            for number in (port, port + 1):
                if number == old_port or number == old_port + 1:
                    continue
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', number))
            temporary = port_file.with_suffix('.tmp')
            temporary.write_text(str(port))
            temporary.replace(port_file)
        cameras = {}
        for facing in ('back', 'front'):
            flag = '-camera-' + facing
            if flag in args:
                value = args[args.index(flag) + 1].replace('\\:', ':')
                if value.startswith('imagefile:'):
                    source = Path(value.split(':', 1)[1]).resolve(strict=True)
                    allowed = HOME / '.cache/serve-emu/camera'
                    if not source.is_relative_to(allowed.resolve()):
                        raise ValueError('Camera placeholders must be in the device hub camera directory')
                    target = ROOT / 'runtime/camera' / (facing + '.png')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    cameras[facing] = str(source)
        if not running:
            for facing in ('back', 'front'):
                if facing not in cameras:
                    (ROOT / f'runtime/camera/{facing}.png').unlink(missing_ok=True)
            (ROOT / 'camera-sources.json').write_text(json.dumps(cameras))
            (ROOT / 'launch-starting').write_text(str(os.getpid()))
        # Update the runtime policy before start so a fast exit cannot restart it.
        if info.returncode == 0:
            docker('update', '--restart=no', CONTAINER, stdout=subprocess.DEVNULL)
        try:
            subprocess.run([HELPER, 'start'], check=True)
        except Exception:
            (ROOT / 'launch-starting').unlink(missing_ok=True)
            raise
        # Explicit T3 shutdown must leave it off, rather than restart the guest.
        docker('update', '--restart=no', CONTAINER, stdout=subprocess.DEVNULL)
        if not running:
            try:
                deadline = time.monotonic() + 160
                while time.monotonic() < deadline:
                    boot = subprocess.run(['docker', 'exec', CONTAINER, str(SDK / 'platform-tools/adb'), '-s', 'emulator-5554', 'shell', 'getprop', 'sys.boot_completed'], capture_output=True, text=True, timeout=8)
                    if boot.returncode == 0 and boot.stdout.strip() == '1':
                        break
                    time.sleep(2)
                else:
                    raise RuntimeError('Android did not finish booting within 160 seconds; inspect launcher.log and host memory pressure')
            except Exception:
                subprocess.run([HELPER, 'stop'], timeout=60)
                raise
            finally:
                (ROOT / 'launch-starting').unlink(missing_ok=True)

    def stop(signum, frame):
        subprocess.run([HELPER, 'stop'], timeout=60)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Stay alive for T3's spawn/exit tracking without owning video or its panel.
    docker('wait', CONTAINER, stdout=subprocess.DEVNULL)


def main():
    os.umask(0o077)
    os.environ.setdefault('DOCKER_HOST', 'tcp://dind:2375')
    args = sys.argv[1:]
    avdmanager = 'avdmanager' in Path(sys.argv[0]).name
    if avdmanager:
        env = dict(os.environ, ANDROID_HOME=str(SDK), ANDROID_SDK_ROOT=str(SDK), ANDROID_USER_HOME=str(STATE), ANDROID_AVD_HOME=str(STATE / 'avd'))
        # Device creation/deletion outside the managed profile is not supported.
        if any(arg in ('create', 'delete', 'move') for arg in args):
            raise ValueError('Manage the persistent phone with agent-hub-android; arbitrary AVD creation/deletion is unsupported')
        os.execve(str(SDK / 'cmdline-tools/latest/bin/avdmanager'), ['avdmanager', *args], env)
    if args == ['-list-avds']:
        if (STATE / f'avd/{AVD}.avd/config.ini').exists():
            print(AVD)
        return
    if not args or any(arg in ('-version', '-help', '--help', '-accel-check', '-help-all') or arg.startswith('-help-') for arg in args):
        # Informational probes do not start the phone. The real executable stays intact.
        if args == ['-accel-check']:
            docker('run', '--rm', '--device', '/dev/kvm', '-v', f'{ROOT}:{ROOT}', '--entrypoint', str(SDK / 'emulator/emulator'), 'agent-hub/android-emulator:1', '-accel-check')
            return
        os.execv(str(SDK / 'emulator/emulator'), ['emulator', *args])
    log = ROOT / 'launcher.log'
    with log.open('a', buffering=1) as output:
        output.write(f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} launch request\n')
        try:
            launch(parse_launch(args), args)
        except Exception as error:
            output.write(f'Launch failed: {error}\n')
            raise


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'agent-hub-emulator: {error}', file=sys.stderr)
        sys.exit(1)
