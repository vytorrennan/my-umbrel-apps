#!/usr/bin/python3
"""Forward npm; wait for the shared server after global OpenCode installs."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request


def real_npm():
    own = Path(__file__).resolve().parent
    paths = [p for p in os.get_exec_path() if Path(p).resolve() != own]
    return shutil.which('npm', path=os.pathsep.join(paths))


def is_opencode_install(args):
    return (any(x in ('install', 'i', 'update', 'up', 'upgrade') for x in args)
            and any(x in ('-g', '--global') for x in args)
            and any(x == '@opencode/cli' or x.startswith('@opencode/cli@') for x in args))


def server_password():
    if os.environ.get('OPENCODE_SERVER_PASSWORD'):
        return os.environ['OPENCODE_SERVER_PASSWORD']
    path = Path(os.environ.get('AGENT_HUB_OPENCODE_CREDENTIAL_FILE',
                               str(Path.home() / '.config/agent-hub/secrets.env')))
    # Agent Hub writes an alphanumeric PW, not arbitrary shell expressions.
    for line in path.read_text().splitlines():
        if line.startswith(('AGENT_PASSWORD=', 'PW=', 'OPENCODE_SERVER_PASSWORD=')):
            return line.split('=', 1)[1].strip().strip('\"\'')
    raise ValueError('Missing shared-server credential')


def reported_version(value):
    if isinstance(value, dict):
        if isinstance(value.get('version'), str):
            return value['version'].lstrip('v')
        for item in value.values():
            found = reported_version(item)
            if found:
                return found
    return None


def wait_for_server():
    binary = os.environ.get('AGENT_HUB_OPENCODE_BINARY', str(Path.home() / '.npm-global/bin/opencode'))
    result = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=5, check=True)
    target = result.stdout.strip().removeprefix('opencode ').lstrip('v')
    credentials = 'opencode:' + server_password()
    header = {'Authorization': 'Basic ' + base64.b64encode(credentials.encode()).decode()}
    url = os.environ.get('AGENT_HUB_OPENCODE_INFO_URL', 'http://127.0.0.1:4096/api/info')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            with opener.open(urllib.request.Request(url, headers=header), timeout=1) as response:
                if reported_version(json.load(response)) == target:
                    print(f'[agent-hub] OpenCode server ready at {target}', flush=True)
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    return False


def main():
    npm = real_npm()
    if npm is None:
        print('[agent-hub] Cannot locate the underlying npm', file=sys.stderr)
        return 127
    args = sys.argv[1:]
    code = subprocess.call([npm, *args])
    if code or not is_opencode_install(args):
        return code
    try:
        if wait_for_server():
            return 0
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    print('[agent-hub] OpenCode installed but the shared server did not become ready', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
