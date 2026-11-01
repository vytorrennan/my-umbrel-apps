"""Focused compatibility checks for the managed SDK facade and console bridge."""
import importlib.machinery
import importlib.util
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch


def load(name):
    path = Path(__file__).with_name(name + '.py')
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AndroidLauncherTests(unittest.TestCase):
    def test_stopped_phone_does_not_run_adb_or_touch_video_settings(self):
        m = load('agent-hub-android')
        class EndIteration(Exception):
            pass
        class Dormant:
            def is_set(self):
                return False
            def wait(self):
                raise EndIteration()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adb = root / 'sdk/platform-tools/adb'
            adb.parent.mkdir(parents=True)
            adb.touch()
            enabled = root / 'enabled'
            enabled.touch()  # Reproduce T3 shutdown leaving the marker set.
            with patch.object(m, 'ROOT', root), patch.object(m, 'SDK', root / 'sdk'), patch.object(m, 'ENABLED', enabled), patch.object(Path, 'home', return_value=root), patch.object(m, 'console_port', return_value=5554), patch.object(m.threading, 'Event', return_value=Dormant()), patch.object(m.threading.Thread, 'start'), patch.object(m, 'EmulatorProxyServer'), patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='emulator-5554')), patch.object(m, 'apply_video_fps') as fps, patch.object(m.time, 'sleep', side_effect=EndIteration):
                try:
                    m.bridge()
                except EndIteration:
                    pass
                fps.assert_not_called()
                m.subprocess.run.assert_not_called()

    def test_runtime_watcher_tracks_start_and_die_events(self):
        m = load('agent-hub-android')
        class EndEvents(Exception):
            pass
        def events():
            yield b'{"Action":"start"}\n'
            yield b'{"Action":"die"}\n'
            raise EndEvents()
        from unittest.mock import MagicMock
        running = MagicMock()
        with patch.object(m.urllib.request, 'build_opener') as opener, patch.object(m.http.client, 'HTTPConnection') as connection:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"State":{"Running":false}}'
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.__iter__.side_effect = events
            with self.assertRaises(EndEvents):
                m.watch_runtime(running)
            self.assertEqual(running.set.call_count, 1)
            self.assertEqual(running.clear.call_count, 2)
            connection.return_value.close.assert_called_once()

    def test_real_t3_launch_arguments_and_invalid_requests(self):
        m = load('agent-hub-emulator')
        args = ['-avd', m.AVD, '-no-audio', '-no-window', '-gpu', 'auto', '-no-boot-anim', '-port', '5556', '-camera-back', 'imagefile\\:/home/developer/.cache/serve-emu/camera/back.png']
        self.assertEqual(m.parse_launch(args), 5556)
        self.assertEqual(m.parse_launch(['@' + m.AVD, '-ports', '5554,5555']), 5554)
        for extra in [['-port', '5555'], ['-wipe-data'], ['-ports', '5554,5557'], ['-camera-back', 'webcam0']]:
            with self.assertRaises(ValueError):
                m.parse_launch(['@' + m.AVD, *extra])
        with self.assertRaises(ValueError):
            m.parse_launch(['@another-phone'])

    def test_facade_replaces_only_known_sdk_alias_and_is_idempotent(self):
        m = load('agent-hub-android')
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            sdk = home / 'Projects/.agent-hub/android/sdk'
            for name in ['emulator/emulator', 'emulator/lib64/library', 'cmdline-tools/latest/bin/avdmanager', 'cmdline-tools/latest/bin/sdkmanager', 'platform-tools/adb']:
                p = sdk / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('original-sdk-bytes')
            (home / 'Android').mkdir()
            (home / 'Android/Sdk').symlink_to(sdk)
            (home / 'Library/Android').mkdir(parents=True)
            (home / 'Library/Android/sdk').symlink_to(sdk)
            (home / '.local/bin').mkdir(parents=True)
            for name in ['emulator', 'avdmanager']:
                (home / '.local/bin' / name).symlink_to(sdk / ('emulator/emulator' if name == 'emulator' else 'cmdline-tools/latest/bin/avdmanager'))
            with patch.object(m, 'SDK', sdk), patch.object(Path, 'home', return_value=home):
                m.install_facade()
                m.install_facade()
            self.assertEqual((sdk / 'emulator/emulator').read_text(), 'original-sdk-bytes')
            self.assertEqual((home / 'Android/Sdk/emulator/emulator').readlink(), Path('/usr/local/bin/agent-hub-emulator'))
            self.assertEqual((home / 'Library/Android/sdk').resolve(), home / 'Android/Sdk')

    def test_fragmented_console_kill_syncs_guest_before_forwarding(self):
        m = load('agent-hub-android')
        local, emulator = socket.socketpair()
        events = []
        server = m.EmulatorProxyServer(('127.0.0.1', 0), m.EmulatorProxy)
        server.remote_port = 5554
        original_connect = socket.create_connection
        def synced(*args, **kwargs):
            events.append('sync')
            return subprocess.CompletedProcess(args, 0)
        def receiver():
            data = b''
            while b'kill\n' not in data:
                data += emulator.recv(1024)
            events.append('kill')
            emulator.close()
        with patch.object(m.socket, 'create_connection', return_value=local), patch.object(m.subprocess, 'run', side_effect=synced):
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            r = threading.Thread(target=receiver, daemon=True)
            r.start()
            client = original_connect(server.server_address)
            client.sendall(b'ki')
            client.sendall(b'll\n')
            client.shutdown(socket.SHUT_WR)
            r.join(3)
            client.close()
            server.shutdown()
            server.server_close()
        self.assertFalse(r.is_alive())
        self.assertEqual(events, ['sync', 'kill'])


if __name__ == '__main__':
    unittest.main()
