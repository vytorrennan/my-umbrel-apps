import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('starter', Path(__file__).with_name('codex-window-starter.py'))
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)


class SchedulingTests(unittest.TestCase):
    def bucket(self, reset, weekly_used=0):
        return {'primary': {'resetsAt': reset},
                'secondary': {'usedPercent': weekly_used, 'resetsAt': 100000}}

    def test_moving_reset_does_not_postpone_persisted_deadline(self):
        state = {}
        self.assertFalse(starter.decision(self.bucket(1000), True, state, 900)[0])
        # Next read synthesizes a reset five hours ahead when the old window expires.
        self.assertTrue(starter.decision(self.bucket(19060), True, state, 1060)[0])

    def test_deadline_survives_process_restart(self):
        self.assertTrue(starter.decision(self.bucket(19060), True, {'next_due': 1060}, 1060)[0])

    def test_success_prevents_duplicate_messages(self):
        self.assertFalse(starter.decision(self.bucket(1000), True,
                                         {'next_due': 19120, 'last_success': 1060}, 1100)[0])

    def test_old_state_migrates_from_last_success(self):
        self.assertTrue(starter.decision(self.bucket(50000), True,
                                        {'last_success': 1000}, 20000)[0])

    def test_ordinary_usage_blocked(self):
        self.assertFalse(starter.decision(self.bucket(1000), False, {'next_due': 1000}, 2000)[0])

    def test_weekly_limit_blocked(self):
        self.assertFalse(starter.decision(self.bucket(1000, 100), True,
                                         {'next_due': 1000}, 2000)[0])


if __name__ == '__main__':
    unittest.main()
