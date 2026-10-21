"""Integration checks for the shared-server updater using a disposable CLI."""
import json
import importlib.util
from unittest.mock import patch
import os
import shutil
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

WRAPPER = Path(__file__).with_name('agent-hub-opencode-server.py')


class SharedServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cli = Path(self.tmp.name) / 'opencode'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.replace('1.0.0')
        self.proc = subprocess.Popen([
            sys.executable, str(WRAPPER), '--poll-interval', '0.05',
            '--settle-seconds', '0.1', '--stop-timeout', '0.5', '--',
            str(self.cli), 'serve', str(self.port)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.wait_version('1.0.0')

    def replace(self, version, broken=False):
        source = f'''#!{sys.executable}
import sys, os, json
from http.server import BaseHTTPRequestHandler, HTTPServer
VERSION = {version!r}
if '--version' in sys.argv:
    print('opencode v' + VERSION)
    raise SystemExit({1 if broken else 0})
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(dict(version=VERSION, pid=os.getpid())).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args): pass
HTTPServer(('127.0.0.1', int(sys.argv[2])), Handler).serve_forever()
'''
        new = self.cli.with_suffix('.new')
        new.write_text(source)
        new.chmod(0o755)
        new.replace(self.cli)

    def info(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}', timeout=0.2) as response:
            return json.load(response)

    def wait_version(self, version):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            try:
                info = self.info()
                if info['version'] == version:
                    return info
            except OSError:
                pass
            self.assertIsNone(self.proc.poll(), 'Wrapper exited unexpectedly')
            time.sleep(0.05)
        self.fail(f'Server did not switch to {version}')

    def tearDown(self):
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.tmp.cleanup()

    def test_update_restarts_server_without_manual_intervention(self):
        original = self.info()['pid']
        self.replace('2.0.0')
        changed = self.wait_version('2.0.0')
        self.assertNotEqual(original, changed['pid'])

    def test_incomplete_update_preserves_server_then_recovers(self):
        original = self.info()['pid']
        self.replace('2.0.0', broken=True)
        time.sleep(0.6)
        self.assertEqual(self.info(), {'version': '1.0.0', 'pid': original})
        self.replace('2.0.0')
        self.wait_version('2.0.0')

    def test_update_command_waits_for_new_server_version(self, persisted_config=False):
        root = Path(self.tmp.name)
        shim = root / 'shim'
        real = root / 'real'
        shim.mkdir()
        real.mkdir()
        shutil.copy2(WRAPPER.with_name('agent-hub-provider-npm.py'), shim / 'npm')
        (shim / 'npm').chmod(0o755)
        replacement = root / 'replacement'
        replacement.write_text(self.cli.read_text().replace("VERSION = '1.0.0'", "VERSION = '2.0.0'"))
        (real / 'npm').write_text(
            f'#!{sys.executable}\nimport shutil, os\n'
            f'shutil.copyfile({str(replacement)!r}, {str(self.cli.with_suffix(".new"))!r})\n'
            f'os.chmod({str(self.cli.with_suffix(".new"))!r}, 0o755)\n'
            f'os.replace({str(self.cli.with_suffix(".new"))!r}, {str(self.cli)!r})\n')
        (real / 'npm').chmod(0o755)
        config = root / '.config/agent-hub'
        config.mkdir(parents=True)
        (config / 'secrets.env').write_text('AGENT_PASSWORD=disposable-test-password\n')
        env = dict(os.environ, PATH=str(shim) + ':' + str(real) + ':' + os.environ['PATH'],
                   HOME=str(root),
                   AGENT_HUB_OPENCODE_BINARY=str(self.cli),
                   AGENT_HUB_OPENCODE_INFO_URL=f'http://127.0.0.1:{self.port}/api/info')
        if persisted_config:
            bridge = root / '.config/opencode-t3/update-bridge.json'
            bridge.parent.mkdir(parents=True, exist_ok=True)
            bridge.write_text(json.dumps({
                'binaryPath': str(self.cli),
                'credentialFile': str(config / 'secrets.env'),
                'infoUrl': f'http://127.0.0.1:{self.port}/api/info'}))
            env.pop('AGENT_HUB_OPENCODE_BINARY', None)
            env.pop('AGENT_HUB_OPENCODE_INFO_URL', None)
        env.pop('OPENCODE_SERVER_PASSWORD', None)
        result = subprocess.run([str(shim / 'npm'), 'install', '-g', '@opencode/cli@latest'],
                                env=env, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        # This is what T3 checks immediately after the installer returns.
        self.assertEqual(self.info()['version'], '2.0.0')

    def test_global_updater_uses_saved_bridge_without_provider_environment(self):
        self.test_update_command_waits_for_new_server_version(persisted_config=True)

    def test_multiple_wrapper_copies_resolve_real_npm_without_recursion(self):
        root = Path(self.tmp.name)
        shim, duplicate, real = [root / x for x in ['shim', 'duplicate', 'real']]
        for folder in [shim, duplicate, real]:
            folder.mkdir()
        source = WRAPPER.with_name('agent-hub-provider-npm.py')
        for folder in [shim, duplicate]:
            shutil.copy2(source, folder / 'npm')
            (folder / 'npm').chmod(0o755)
        (real / 'npm').write_text('#!/bin/sh\nexit 0\n')
        (real / 'npm').chmod(0o755)
        spec = importlib.util.spec_from_file_location('npm_under_test', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.__file__ = str(shim / 'npm')
        with patch.dict(os.environ, {'PATH': ':'.join(map(str, [shim, duplicate, real]))}):
            self.assertEqual(module.real_npm(), str(real / 'npm'))

    def test_same_version_reinstall_does_not_restart_and_stop_cleans_up(self):
        original = self.info()['pid']
        self.replace('1.0.0')
        time.sleep(0.5)
        self.assertEqual(self.info()['pid'], original)
        self.proc.terminate()
        self.proc.wait(timeout=3)
        with self.assertRaises(OSError):
            self.info()


if __name__ == '__main__':
    unittest.main()
