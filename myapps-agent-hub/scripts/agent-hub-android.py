#!/usr/bin/python3
"""Manage the optional Android emulator in Agent Hub's existing DinD daemon."""
import argparse
import atexit
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import secrets
import select
import socket
import socketserver
import subprocess
import threading
import time
import urllib.request
import urllib.parse
import zipfile

ROOT = Path.home() / 'Projects/.agent-hub/android'
SDK = ROOT / 'sdk'
STATE = ROOT / 'user'
BUNDLE = Path('/usr/local/lib/agent-hub/android')
IMAGE = 'agent-hub/android-emulator:1'
CONTAINER = 'agent-hub-android'
AVD = 'AgentHub_Pixel_Android_11'
PACKAGE = 'system-images;android-30;default;x86_64'
ENABLED = Path.home() / '.config/agent-hub/android-enabled'
PORT_FILE = ROOT / 'console-port'


def console_port():
    try:
        port = int(PORT_FILE.read_text())
    except FileNotFoundError:
        return 5554
    if port < 5554 or port > 5682 or port % 2:
        raise ValueError('Invalid managed emulator console port')
    return port


def serial():
    return f'emulator-{console_port()}'


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def link_home(name, destination):
    link = Path.home() / name
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and link.resolve() == destination.resolve():
        return
    if link.exists() or link.is_symlink():
        raise RuntimeError(f'Preserve existing {link}; move it before setup')
    link.symlink_to(destination)


def stop_container():
    # QEMU stopping is not a guest shutdown. Flush Android's filesystem first
    # so a just-written file is not left only in the guest's page cache.
    adb = SDK / 'platform-tools/adb'
    if adb.exists():
        try:
            synced = subprocess.run([str(adb), '-s', serial(), 'shell', 'sync'], capture_output=True, timeout=20)
            if synced.returncode:
                print('Android offline; stopping without a guest sync', flush=True)
        except subprocess.TimeoutExpired:
            print('Android sync timed out; stopping runtime', flush=True)
    run(['docker', 'stop', '-t', '30', CONTAINER])


def install_facade():
    facade = Path.home() / 'Android/Sdk'
    if facade.is_symlink() and facade.resolve() == SDK.resolve():
        facade.unlink()
    facade.mkdir(parents=True, exist_ok=True)
    for entry in SDK.iterdir():
        if entry.name in ('emulator', 'cmdline-tools'):
            continue
        link_home(str((facade / entry.name).relative_to(Path.home())), entry)
    emulator_dir = facade / 'emulator'
    emulator_dir.mkdir(exist_ok=True)
    for entry in (SDK / 'emulator').iterdir():
        target = Path('/usr/local/bin/agent-hub-emulator') if entry.name == 'emulator' else entry
        link_home(str((emulator_dir / entry.name).relative_to(Path.home())), target)
    tools = facade / 'cmdline-tools/latest/bin'
    tools.mkdir(parents=True, exist_ok=True)
    for entry in (SDK / 'cmdline-tools/latest/bin').iterdir():
        target = Path('/usr/local/bin/agent-hub-avdmanager') if entry.name == 'avdmanager' else entry
        link_home(str((tools / entry.name).relative_to(Path.home())), target)
    alias = Path.home() / 'Library/Android/sdk'
    if alias.is_symlink() and alias.resolve() == SDK.resolve():
        alias.unlink()
    link_home('Library/Android/sdk', facade)
    for name in ('emulator', 'avdmanager'):
        link = Path.home() / '.local/bin' / name
        if link.is_symlink() and link.resolve().is_relative_to(SDK):
            link.unlink()
        link_home(str(link.relative_to(Path.home())), Path('/usr/local/bin/agent-hub-' + name))


def setup():
    if shutil.which('java') is None:
        raise RuntimeError('Java 17 or newer is required')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.mkdir(exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    STATE.chmod(0o700)
    SDK.mkdir(exist_ok=True)
    # Never replace mapped emulator executables/libraries while it is running.
    existing = subprocess.run(['docker', 'container', 'inspect', CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if existing.returncode == 0:
        stop_container()
        run(['docker', 'rm', CONTAINER])
    manager = SDK / 'cmdline-tools/latest/bin/sdkmanager'
    if not manager.exists():
        archive = ROOT / 'commandline-tools.zip'
        urllib.request.urlretrieve('https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip', archive)
        if hashlib.sha1(archive.read_bytes()).hexdigest() != '48833c34b761c10cb20bcd16582129395d121b27':
            raise RuntimeError('Android command-line tools checksum mismatch')
        tools = SDK / 'cmdline-tools'
        tools.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as source:
            source.extractall(tools)
        (tools / 'cmdline-tools').rename(tools / 'latest')
        for executable in (tools / 'latest/bin').iterdir():
            executable.chmod(0o755)
        archive.unlink()
    install_facade()
    # expo-device-hub 0.15.3 defaults to this path even on Linux when the
    # already-running T3 process has no ANDROID_HOME environment variable.
    # Keep the main ADB state separate. Only the DinD container has KVM and
    # should see the AVD; otherwise T3 offers a second, unusable local boot.
    android_home = Path.home() / '.android'
    android_home.mkdir(exist_ok=True, mode=0o700)
    run([manager, '--sdk_root=' + str(SDK), '--licenses'], input='y\n' * 100, text=True)
    run([manager, '--sdk_root=' + str(SDK), 'platform-tools', 'emulator', PACKAGE], input='y\n' * 100, text=True)
    for name, binary in {'adb': SDK / 'platform-tools/adb', 'sdkmanager': manager}.items():
        link_home('.local/bin/' + name, binary)
    run([SDK / 'platform-tools/adb', 'start-server'])
    for name in ('adbkey', 'adbkey.pub'):
        key = android_home / name
        if key.exists():
            shutil.copy2(key, STATE / name)
            (STATE / name).chmod(0o600)
    env = dict(os.environ, ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(STATE), ANDROID_AVD_HOME=str(STATE / 'avd'))
    old = STATE / 'avd/AgentHub_Android_11.avd'
    if old.exists() and not (STATE / f'avd/{AVD}.avd').exists():
        old.rename(STATE / f'avd/{AVD}.avd')
        old_ini = STATE / 'avd/AgentHub_Android_11.ini'
        ini = old_ini.read_text().replace('AgentHub_Android_11', AVD)
        (STATE / f'avd/{AVD}.ini').write_text(ini)
        old_ini.unlink()
    existing_config = STATE / f'avd/{AVD}.avd/config.ini'
    if existing_config.exists():
        current = dict(tuple(part.strip() for part in line.split('=', 1)) for line in existing_config.read_text().splitlines() if '=' in line)
        if 'system-images/android-30/default/x86_64' not in current.get('image.sysdir.1', ''):
            backup = ROOT / 'backups' / f'{AVD}-{time.time_ns()}'
            backup.mkdir(parents=True, mode=0o700)
            (STATE / f'avd/{AVD}.avd').rename(backup / f'{AVD}.avd')
            (STATE / f'avd/{AVD}.ini').rename(backup / f'{AVD}.ini')
            print(f'Preserved previous Android phone at {backup}', flush=True)
    if not (STATE / f'avd/{AVD}.avd/config.ini').exists():
        run([SDK / 'cmdline-tools/latest/bin/avdmanager', 'create', 'avd', '--name', AVD, '--package', PACKAGE, '--device', 'pixel_2'], env=env, input='no\n', text=True)
    config = STATE / f'avd/{AVD}.avd/config.ini'
    values = dict(tuple(part.strip() for part in line.split('=', 1)) for line in config.read_text().splitlines() if '=' in line)
    values.update({'AvdId': AVD, 'avd.ini.displayname': AVD, 'hw.ramSize': '2048', 'hw.cpu.ncore': '2', 'hw.lcd.width': '480', 'hw.lcd.height': '800', 'hw.lcd.density': '160', 'hw.gpu.enabled': 'yes', 'hw.gpu.mode': 'swiftshader', 'disk.dataPartition.size': '6G'})
    config.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    run(['docker', 'build', '-t', IMAGE, BUNDLE])
    start()


def start():
    if not (STATE / f'avd/{AVD}.avd/config.ini').exists():
        raise RuntimeError('Run agent-hub-android setup first')
    exists = subprocess.run(['docker', 'container', 'inspect', CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    running = exists and run(['docker', 'inspect', '--format', '{{.State.Running}}', CONTAINER], capture_output=True, text=True).stdout.strip() == 'true'
    if not running:
        # Rebuild the small runtime only when its bundled source changed. SDK
        # packages and phone data stay on their existing bind mount.
        digest = hashlib.sha256(b''.join((BUNDLE / name).read_bytes() for name in ('Dockerfile', 'entrypoint.sh'))).hexdigest()
        label = 'io.agent-hub.android.bundle-sha256'
        current = subprocess.run(['docker', 'image', 'inspect', '--format', '{{index .Config.Labels "' + label + '"}}', IMAGE], capture_output=True, text=True)
        if current.returncode or current.stdout.strip() != digest:
            run(['docker', 'build', '--label', label + '=' + digest, '-t', IMAGE, BUNDLE])
        if exists:
            old = run(['docker', 'inspect', '--format', '{{.Image}}', CONTAINER], capture_output=True, text=True).stdout.strip()
            new = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE], capture_output=True, text=True).stdout.strip()
            if old != new:
                run(['docker', 'rm', CONTAINER])
                exists = False
    if exists:
        run(['docker', 'update', '--restart=no', CONTAINER])
        run(['docker', 'start', CONTAINER])
    else:
        (ROOT / 'runtime').mkdir(exist_ok=True, mode=0o700)
        token = STATE / 'console-auth-token'
        console = Path.home() / '.emulator_console_auth_token'
        if not token.exists():
            token.write_bytes(console.read_bytes() if console.exists() else secrets.token_hex(24).encode())
        token.chmod(0o600)
        # adb refuses symlinked console credentials. Keep a matching regular
        # file here; the emulator receives the persistent token by file mount.
        if console.is_symlink() and console.resolve() == token.resolve():
            console.unlink()
        if not console.exists():
            shutil.copy2(token, console)
        elif console.read_bytes() != token.read_bytes():
            raise RuntimeError('Existing console credential differs; preserve it before setup')
        console.chmod(0o600)
        group = run(['docker', 'run', '--rm', '--device', '/dev/kvm', '--entrypoint', '/usr/bin/stat', IMAGE, '-c', '%g', '/dev/kvm'], capture_output=True, text=True).stdout.strip()
        run(['docker', 'run', '-d', '--name', CONTAINER, '--restart', 'no', '--init', '--device', '/dev/kvm', '--user', f'{os.getuid()}:{os.getgid()}', '--group-add', group, '--cpus', '3', '--memory', '3072m', '--memory-swap', '4096m', '--shm-size', '256m', '-v', f'{ROOT}:{ROOT}', '-v', f'{token}:{Path.home()}/.emulator_console_auth_token', '-p', '5555:5556', '-p', '5554:5557', '-p', '8554:8555', '-e', 'XDG_RUNTIME_DIR=' + str(ROOT / 'runtime'), '-e', 'HOME=' + str(Path.home()), '-e', 'ANDROID_HOME=' + str(SDK), '-e', 'ANDROID_USER_HOME=' + str(STATE), '-e', 'ANDROID_EMULATOR_HOME=' + str(STATE), '-e', 'ANDROID_AVD_HOME=' + str(STATE / 'avd'), '-e', 'ADB_VENDOR_KEYS=' + str(STATE), IMAGE])
    ENABLED.parent.mkdir(parents=True, exist_ok=True)
    ENABLED.touch()


class EmulatorProxy(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(('dind', self.server.remote_port), timeout=10) as remote:
                remote.settimeout(None)
                readers = {self.request, remote}
                console_buffer = b''
                while readers:
                    readable, _, _ = select.select(list(readers), [], [])
                    for current in readable:
                        data = current.recv(65536)
                        other = remote if current is self.request else self.request
                        if not data:
                            # A peer can half-close a request while still
                            # waiting for a reply in the reverse direction.
                            readers.remove(current)
                            other.shutdown(socket.SHUT_WR)
                        else:
                            if current is self.request and self.server.remote_port == 5554:
                                console_buffer += data
                                while b'\n' in console_buffer:
                                    line, console_buffer = console_buffer.split(b'\n', 1)
                                    if line.strip() == b'kill':
                                        try:
                                            synced = subprocess.run(['docker', 'exec', CONTAINER, str(SDK / 'platform-tools/adb'), '-s', 'emulator-5554', 'shell', 'sync'], capture_output=True, timeout=20)
                                            if synced.returncode:
                                                raise OSError('Guest sync failed')
                                        except (OSError, subprocess.TimeoutExpired):
                                            self.request.sendall(b'KO: guest sync failed; emulator remains running\r\n')
                                            return
                                    remote.sendall(line + b'\n')
                                if len(console_buffer) > 65536:
                                    return
                                continue
                            other.sendall(data)
        except OSError:
            return


class EmulatorProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def apply_video_fps():
    """Use the hub's settings API without changing installed T3 packages."""
    hub_file = Path.home() / '.t3/userdata/device/agent-device/hub.json'
    try:
        hub = json.loads(hub_file.read_text())
        os.kill(int(hub['pid']), 0)
        port = int(hub['port'])
        if not 1 <= port <= 65535:
            return
        url = f'http://127.0.0.1:{port}/vendor/serve-emu/api/stream-settings?device={serial()}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=3) as response:
            current = json.load(response)
        if current.get('ok') and current.get('h264Fps') != 24:
            request = urllib.request.Request(url, data=b'{"h264Fps":24}', headers={'Content-Type': 'application/json'}, method='PATCH')
            with opener.open(request, timeout=15) as response:
                updated = json.load(response)
            if updated.get('ok') and updated.get('h264Fps') == 24:
                print('Android video configured at 24 FPS', flush=True)
    except (OSError, ValueError, KeyError):
        # Missing/idle hubs are normal. Never start a stream or shut one down.
        return


def watch_runtime(running):
    """Block on DinD events rather than polling a stopped Android guest."""
    endpoint = urllib.parse.urlparse(os.environ.get('DOCKER_HOST', 'tcp://dind:2375'))
    if endpoint.scheme not in ('tcp', 'http') or not endpoint.hostname:
        raise RuntimeError('Android event watcher requires the configured plain TCP DinD endpoint')
    while True:
        connection = None
        try:
            since = str(int(time.time()))
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    f'http://{endpoint.netloc}/containers/{CONTAINER}/json', timeout=5
                ) as response:
                    active = json.load(response)['State']['Running']
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                active = False
            if active:
                running.set()
            else:
                running.clear()
            filters = json.dumps({'type': ['container'], 'container': [CONTAINER], 'event': ['start', 'die', 'destroy']})
            connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port or 2375, timeout=5)
            connection.request('GET', '/events?' + urllib.parse.urlencode({'since': since, 'filters': filters}))
            response = connection.getresponse()
            if response.status != 200:
                raise OSError('DinD event stream unavailable')
            connection.sock.settimeout(None)
            for line in response:
                event = json.loads(line)
                action = event.get('Action', event.get('status'))
                if action == 'start':
                    running.set()
                elif action in ('die', 'destroy'):
                    running.clear()
            raise OSError('DinD event stream ended')
        except (OSError, ValueError, KeyError, http.client.HTTPException):
            running.clear()
            time.sleep(5)
        finally:
            if connection is not None:
                connection.close()


def bridge():
    adb = SDK / 'platform-tools/adb'
    servers = []
    bound_port = None
    discovery = Path.home() / f'.android/avd/running/pid_{os.getpid()}_info.ini'
    atexit.register(lambda: discovery.unlink(missing_ok=True))
    running = threading.Event()
    threading.Thread(target=watch_runtime, args=(running,), daemon=True).start()
    while True:
        if not running.is_set():
            for server in servers:
                server.shutdown()
                server.server_close()
            servers = []
            discovery.unlink(missing_ok=True)
            running.wait()
        port = console_port()
        starting = ROOT / 'launch-starting'
        if starting.exists():
            try:
                os.kill(int(starting.read_text()), 0)
            except (ProcessLookupError, ValueError):
                starting.unlink(missing_ok=True)
        # T3 treats ADB online as ready for video. Gate publication during cold
        # boot so video capture cannot race guest startup and fail immediately.
        enabled = running.is_set() and ENABLED.exists() and adb.exists() and not starting.exists()
        if servers and (not enabled or bound_port != port):
            for server in servers:
                server.shutdown()
                server.server_close()
            servers = []
            discovery.unlink(missing_ok=True)
        if enabled:
            if not servers:
                for local, remote in ((port, 5554), (port + 1, 5555), (8554, 8554)):
                    server = EmulatorProxyServer(('127.0.0.1', local), EmulatorProxy)
                    server.remote_port = remote
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                    servers.append(server)
                bound_port = port
            try:
                # Publish the authenticated endpoint under this bridge's live
                # PID, since the emulator PID belongs to another namespace.
                files = sorted((ROOT / 'runtime/avd/running').glob('pid_*.ini'), key=lambda p: p.stat().st_mtime, reverse=True)
                if files:
                    values = dict(tuple(part.strip() for part in line.split('=', 1)) for line in files[0].read_text().splitlines() if '=' in line)
                    token = values.get('grpc.token', '').strip()
                    if token:
                        discovery.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        temporary = discovery.with_suffix('.tmp')
                        temporary.write_text(f'port.serial={port}\ngrpc.port=8554\navd.name={AVD}\ngrpc.token={token}\n')
                        temporary.chmod(0o600)
                        temporary.replace(discovery)
                listed = subprocess.run([str(adb), 'devices'], capture_output=True, text=True, timeout=10)
                if serial() not in listed.stdout:
                    request = f'host:emulator:{port + 1}'.encode()
                    with socket.create_connection(('127.0.0.1', 5037), timeout=5) as connection:
                        connection.sendall(f'{len(request):04x}'.encode() + request)
                        connection.recv(4)
            except (OSError, subprocess.TimeoutExpired):
                pass
            try:
                sources = json.loads((ROOT / 'camera-sources.json').read_text())
                for facing, filename in sources.items():
                    source = Path(filename).resolve()
                    if facing in ('back', 'front') and source.is_relative_to((Path.home() / '.cache/serve-emu/camera').resolve()):
                        target = ROOT / f'runtime/camera/{facing}.png'
                        if not target.exists() or source.stat().st_mtime_ns != target.stat().st_mtime_ns:
                            temporary = target.with_suffix('.tmp')
                            shutil.copy2(source, temporary)
                            temporary.replace(target)
            except (OSError, ValueError):
                pass
            apply_video_fps()
        time.sleep(2)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'start', 'stop', 'status', 'bridge', 'install-facade'])
    command = parser.parse_args().command
    if command == 'install-facade':
        if SDK.exists():
            install_facade()
        return
    if command == 'stop':
        stop_container()
        ENABLED.unlink(missing_ok=True)
    elif command == 'status':
        run(['docker', 'inspect', '--format', '{{.State.Status}}', CONTAINER])
        run([SDK / 'platform-tools/adb', 'devices', '-l'])
    else:
        globals()[command]()


if __name__ == '__main__':
    main()
