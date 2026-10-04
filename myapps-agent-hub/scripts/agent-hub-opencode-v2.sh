#!/usr/bin/env bash
# Upgrade npm tools hidden by an existing /home/developer volume, before startup.
set -euo pipefail

DEV_HOME=/home/developer
export PATH="$DEV_HOME/.npm-global/bin:$DEV_HOME/.fnm/aliases/default/bin:$DEV_HOME/.fnm/current/bin:$DEV_HOME/.fnm:$DEV_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
OPENCODE_VERSION="${OPENCODE_VERSION:-2.0.22}"
OPENCHAMBER_VERSION="${OPENCHAMBER_VERSION:-2.1.0}"
command -v node >/dev/null
command -v npm >/dev/null

needs_upgrade() {
  node - "$DEV_HOME/.npm-global/lib/node_modules/$1/package.json" "$2" <<'JS'
const fs = require('node:fs')
try {
  const installed = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).version
  const target = process.argv[3].split('.').map(Number)
  if (!/^\d+\.\d+\.\d+$/.test(installed)) process.exit(0)
  const current = installed.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    if (current[i] !== target[i]) process.exit(current[i] < target[i] ? 0 : 1)
  }
  process.exit(1)
} catch {
  process.exit(0)
}
JS
}

UPDATE_OPENCODE=false
UPDATE_OPENCHAMBER=false
if needs_upgrade @opencode/cli "$OPENCODE_VERSION" || ! opencode --version >/dev/null 2>&1; then
  UPDATE_OPENCODE=true
fi
if needs_upgrade @openchamber/web "$OPENCHAMBER_VERSION"; then
  UPDATE_OPENCHAMBER=true
fi
if [ "$UPDATE_OPENCODE" = false ] && [ "$UPDATE_OPENCHAMBER" = false ]; then
  exit 0
fi

# Keep config files in their supported V1 format. V2 normalizes them in memory.
# Back up credentials and the database before V2 performs its automatic migration.
python3 - <<'PY'
from pathlib import Path
import shutil
import sqlite3
import tempfile

home = Path('/home/developer')
root = home / '.local/share/opencode-upgrade-backups'
root.mkdir(parents=True, exist_ok=True, mode=0o700)
backup = Path(tempfile.mkdtemp(prefix='container-v2-', dir=root))
for name in ('opencode', 'openchamber'):
    config = home / '.config' / name
    if config.exists():
        shutil.copytree(config, backup / 'config' / name,
                        ignore=shutil.ignore_patterns('node_modules'), symlinks=True)
data = home / '.local/share/opencode'
if data.exists():
    (backup / 'data').mkdir(mode=0o700)
    for path in data.glob('*.json'):
        shutil.copy2(path, backup / 'data' / path.name)
    if (data / 'opencode.db').exists():
        with sqlite3.connect(f'file:{data}/opencode.db?mode=ro', uri=True) as src:
            with sqlite3.connect(backup / 'data/opencode.db') as dst:
                src.backup(dst)
print(f'[opencode-v2] Backup: {backup}')
PY

npm config set prefix "$DEV_HOME/.npm-global"
if [ "$UPDATE_OPENCODE" = true ]; then
  npm uninstall -g opencode-ai
  npm install -g --allow-scripts=@opencode/cli "@opencode/cli@$OPENCODE_VERSION"
  opencode --version
fi
if [ "$UPDATE_OPENCHAMBER" = true ]; then
  npm install -g --allow-scripts=node-pty,msgpackr-extract "@openchamber/web@$OPENCHAMBER_VERSION"
fi
