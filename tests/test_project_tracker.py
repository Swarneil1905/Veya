"""Behavior tests for delivery bookkeeping; these do not mark product stories done."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = ROOT / 'artifacts/tracker-tests'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
module_path = Path(os.environ.get('VEYA_TRACKER_MODULE', ROOT / 'scripts/project.py'))
spec = importlib.util.spec_from_file_location('project_tracker', module_path)
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.data = tracker.load(ROOT)
        # Exercise lifecycle rules independently of the real project's progress.
        for story in self.data['stories']:
            story.update(status='backlog', commit=None, evidence=[],
                         acceptance_note=None, actual_hours=None, blocked_reason=None)
        for epic in self.data['epics']:
            epic.update(acceptance_status='pending', acceptance_evidence=[], accepted_at=None)
        self.data['history'] = []

    def test_initial_backlog_is_complete_and_not_claimed_done(self):
        tracker.validate(self.data)
        self.assertGreaterEqual(len(self.data['stories']), 240)
        self.assertGreaterEqual(len(self.data['epics']), 24)
        self.assertEqual(tracker.summary(self.data)['status_counts']['done'], 0)

    def test_only_dependency_free_first_story_is_ready(self):
        ready = tracker.ready_stories(self.data)
        self.assertIn('VEY-001', [s['id'] for s in ready])
        self.assertTrue(all(not s['depends_on'] for s in ready))

    def test_duplicate_ids_fail(self):
        self.data['stories'][1]['id'] = 'VEY-001'
        with self.assertRaisesRegex(ValueError, 'Duplicate story ID'):
            tracker.validate(self.data)

    def test_unknown_dependency_fails(self):
        self.data['stories'][0]['depends_on'] = ['VEY-999']
        with self.assertRaisesRegex(ValueError, 'Unknown dependency'):
            tracker.validate(self.data)

    def test_dependency_cycle_fails(self):
        self.data['stories'][0]['depends_on'] = ['VEY-002']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            tracker.validate(self.data)

    def test_documentation_only_story_fails(self):
        self.data['stories'][0]['code_paths'] = ['docs/notes.md']
        with self.assertRaisesRegex(ValueError, 'Documentation-only'):
            tracker.validate(self.data)

    def test_release_missing_prerequisite_fails(self):
        self.data['releases'][0]['story_ids'].remove('VEY-001')
        with self.assertRaisesRegex(ValueError, 'omits prerequisites'):
            tracker.validate(self.data)

    def test_dependent_story_cannot_start_early(self):
        with self.assertRaisesRegex(ValueError, 'dependencies'):
            tracker.transition(ROOT, self.data, 'VEY-002', 'in_progress')

    def test_blocking_requires_reason_and_preserves_history(self):
        with self.assertRaisesRegex(ValueError, 'reason'):
            tracker.transition(ROOT, self.data, 'VEY-001', 'blocked')
        tracker.transition(ROOT, self.data, 'VEY-001', 'blocked', reason='Clean test machine unavailable')
        self.assertEqual(self.data['history'][-1]['to'], 'blocked')
        tracker.transition(ROOT, self.data, 'VEY-001', 'backlog')
        self.assertIsNone(self.data['stories'][0]['blocked_reason'])

    def test_done_cannot_skip_review(self):
        with self.assertRaisesRegex(ValueError, 'Invalid transition'):
            tracker.transition(ROOT, self.data, 'VEY-001', 'done')

    def test_done_requires_real_commit(self):
        tracker.transition(ROOT, self.data, 'VEY-001', 'in_progress')
        tracker.transition(ROOT, self.data, 'VEY-001', 'in_review')
        with self.assertRaisesRegex(ValueError, 'commit ID'):
            tracker.transition(ROOT, self.data, 'VEY-001', 'done')
        self.assertEqual(self.data['stories'][0]['status'], 'in_review')

    def test_actual_hours_reject_nan(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            tracker.transition(ROOT, self.data, 'VEY-001', 'in_progress', actual_hours=float('nan'))

    def test_deliverable_cannot_be_accepted_with_unfinished_stories(self):
        self.data['epics'][0]['acceptance_status'] = 'accepted'
        self.data['epics'][0]['acceptance_evidence'] = ['some-file.txt']
        with self.assertRaisesRegex(ValueError, 'Accepted deliverable'):
            tracker.validate(self.data)

    def test_concurrent_tracker_lock_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            root = Path(directory)
            (root/'planning').mkdir()
            with tracker.locked(root):
                with self.assertRaisesRegex(ValueError, 'lock'):
                    with tracker.locked(root):
                        self.fail('Second writer entered')
            self.assertFalse((root/'planning/.tracker.lock').exists())

    def test_atomic_save_and_generated_views_agree(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            root = Path(directory)
            (root/'planning').mkdir()
            tracker.save(self.data, root)
            tracker.render(self.data, root)
            self.assertEqual(tracker.load(root), self.data)
            issues = json.loads((root/'planning/github-issues.json').read_text())
            self.assertFalse(issues['published'])
            self.assertEqual(len(issues['issues']), len(self.data['stories']))
            markdown = (root/'planning/BACKLOG.md').read_text(encoding='utf-8')
            self.assertEqual(markdown.count('## VEY-'), len(self.data['stories']))

    def test_completion_accepts_real_code_commit_and_rejects_fake_evidence(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args], check=True, capture_output=True, text=True).stdout.strip()
            git('init','--initial-branch=main')
            (root/'package.json').write_text('{}\n')
            git('add','package.json')
            git('-c','user.name=Tracker Test','-c','user.email=tracker@example.invalid','commit','-qm','baseline')
            self.data['project']['baseline_commit'] = git('rev-parse','HEAD')
            (root/'package.json').write_text('{"name":"veya-test"}\n')
            (root/'evidence.txt').write_text('Test command: isolated fixture check. Result: passed.\n')
            git('add','package.json','evidence.txt')
            git('-c','user.name=Tracker Test','-c','user.email=tracker@example.invalid','commit','-qm','change package code')
            commit = git('rev-parse','HEAD')
            tracker.transition(root,self.data,'VEY-001','in_progress')
            tracker.transition(root,self.data,'VEY-001','in_review')
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                tracker.transition(root,self.data,'VEY-001','done',commit=commit,evidence=['missing.txt'],note='Acceptance assessed in isolated test')
            tracker.transition(root,self.data,'VEY-001','done',commit=commit,evidence=['evidence.txt'],note='Acceptance assessed in isolated test',actual_hours=4)
            self.assertEqual(self.data['stories'][0]['status'],'done')
            self.assertEqual(self.data['stories'][0]['actual_hours'],4)
            self.assertIn('VEY-002',[s['id'] for s in tracker.ready_stories(self.data)])
            tracker.transition(root,self.data,'VEY-001','in_progress',reason='Reproduced regression in fixture')
            self.assertIsNone(self.data['stories'][0]['commit'])


if __name__ == '__main__':
    unittest.main()
