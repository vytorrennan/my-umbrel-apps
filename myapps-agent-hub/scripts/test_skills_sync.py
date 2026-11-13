import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).with_name('skills-sync.py')
spec = importlib.util.spec_from_loader('skills_sync', loader=None)
skills_sync = importlib.util.module_from_spec(spec)
exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'), skills_sync.__dict__)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src, self.dst, self.ignore = root / 'src', root / 'dst', root / 'cfg' / 'ignore'
        for name in ('alpha', 'beta', 'synced', '.hidden'):
            (self.src / name).mkdir(parents=True)
        (self.dst / 'synced' / 'account' / 'docx').mkdir(parents=True)
        (self.dst / 'claude-mine').mkdir()
        skills_sync.STATE_DIR = root / 'state'
        self.ctx = skills_sync.Ctx(self.src, self.dst, self.ignore)

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self):
        return skills_sync.sync_once(self.ctx)

    def test_links_shared_skills_and_creates_default_ignore_file(self):
        self.sync()
        self.assertEqual(os.readlink(self.dst / 'alpha'), str(self.src / 'alpha'))
        self.assertTrue((self.dst / 'beta').is_symlink())
        self.assertIn('synced', self.ignore.read_text())

    def test_never_touches_synced_hidden_or_claude_only_folders(self):
        self.sync()
        self.assertFalse((self.dst / 'synced').is_symlink())
        self.assertTrue((self.dst / 'synced' / 'account' / 'docx').is_dir())
        self.assertFalse((self.dst / '.hidden').exists())
        self.assertTrue((self.dst / 'claude-mine').is_dir())

    def test_claude_only_folder_wins_a_name_clash(self):
        (self.dst / 'beta').mkdir()
        _actions, report = self.sync()
        self.assertFalse((self.dst / 'beta').is_symlink())
        self.assertEqual([name for name, _ in report['conflicts']], ['beta'])

    def test_leaves_foreign_symlinks_alone(self):
        elsewhere = Path(self.tmp.name) / 'elsewhere'
        elsewhere.mkdir()
        os.symlink(elsewhere, self.dst / 'alpha')
        self.sync()
        self.assertEqual(os.readlink(self.dst / 'alpha'), str(elsewhere))

    def test_removes_links_for_deleted_and_newly_ignored_skills(self):
        self.sync()
        (self.src / 'alpha').rmdir()
        self.ignore.write_text(self.ignore.read_text() + 'be*\n')
        self.sync()
        self.assertFalse(os.path.lexists(self.dst / 'alpha'))
        self.assertFalse(os.path.lexists(self.dst / 'beta'))

    def test_negated_pattern_unignores(self):
        rules = [(False, '*'), (True, 'alpha')]
        self.assertFalse(skills_sync.is_ignored('alpha', rules))
        self.assertTrue(skills_sync.is_ignored('beta', rules))

    def test_second_sync_is_a_no_op(self):
        self.sync()
        actions, _report = self.sync()
        self.assertEqual(actions, [])

    def test_watch_links_new_skill_and_restores_deleted_link(self):
        env = dict(os.environ, XDG_STATE_HOME=str(Path(self.tmp.name) / 'state'))
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), 'watch', '--source', str(self.src),
             '--target', str(self.dst), '--ignore-file', str(self.ignore)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        try:
            self.wait_for(lambda: (self.dst / 'alpha').is_symlink())
            (self.src / 'gamma').mkdir()
            self.wait_for(lambda: (self.dst / 'gamma').is_symlink())
            (self.dst / 'gamma').unlink()
            self.wait_for(lambda: (self.dst / 'gamma').is_symlink())
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def wait_for(self, condition, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if condition():
                return
            time.sleep(0.05)
        self.fail('condition not met in time')


if __name__ == '__main__':
    unittest.main()
