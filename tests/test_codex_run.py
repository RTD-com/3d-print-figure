"""Windows-only launcher tests use a local fake CLI; no Codex/API execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PS = shutil.which('powershell')


@unittest.skipUnless(os.name == 'nt' and PS, 'Windows PowerShell launcher tests')
class CodexLauncherTests(unittest.TestCase):
    def run_fake(self, mode, extra=()):
        with tempfile.TemporaryDirectory(prefix='codex-launcher-', dir=ROOT / '.tmp') as temp:
            temp = Path(temp)
            work = temp / 'work'
            work.mkdir()
            prompt = temp / 'prompt.txt'
            prompt.write_text('offline fake only', encoding='utf-8')
            fake = temp / 'fake.py'
            fake.write_text('''import json,os,sys,time
from pathlib import Path
mode=os.environ['FAKE_CODEX_MODE']
counter=Path(os.environ['FAKE_CODEX_COUNTER'])
count=int(counter.read_text())+1 if counter.exists() else 1
counter.write_text(str(count))
args=sys.argv[1:]
if mode=='timeout':
 print('started',flush=True)
 time.sleep(15)
if mode=='refresh' and count==1:
 print('failed to refresh available models: request timed out',file=sys.stderr)
 sys.exit(3)
if mode=='task-failure':
 print(json.dumps({'type':'item.completed'}))
 Path('artifact.txt').write_text('already generated')
 sys.exit(4)
if mode!='no-last':
 Path(args[args.index('--output-last-message')+1]).write_text('result',encoding='utf-8')
sys.exit(0)
''', encoding='utf-8')
            shim = temp / 'fake.cmd'
            shim.write_text('@"%FAKE_CODEX_PYTHON%" "%FAKE_CODEX_SCRIPT%" %*\n', encoding='ascii')
            env = dict(os.environ, FAKE_CODEX_MODE=mode, FAKE_CODEX_COUNTER=str(temp / 'counter'),
                       FAKE_CODEX_PYTHON=sys.executable, FAKE_CODEX_SCRIPT=str(fake))
            command = [PS, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                       str(ROOT / 'scripts' / 'codex_run.ps1'), '-PromptFile', str(prompt),
                       '-Workdir', str(work), '-CodexExe', str(shim), '-RetryDelaySec', '0',
                       '-TimeoutSec', '1' if mode == 'timeout' else '10'] + list(extra)
            proc = subprocess.run(command, env=env, capture_output=True, timeout=35)
            summaries = list(work.rglob('*-run.json'))
            summary = json.loads(summaries[0].read_text(encoding='utf-8')) if summaries else None
            logs = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in work.rglob('*.log'))
            return proc.returncode, summary, proc.stdout.decode(errors='replace') + proc.stderr.decode(errors='replace') + logs

    @classmethod
    def setUpClass(cls):
        (ROOT / '.tmp').mkdir(exist_ok=True)

    def test_zero_exit_without_last_message_fails_consistently(self):
        code, summary, output = self.run_fake('no-last')
        self.assertEqual(1, code, output)
        self.assertFalse(summary['ok'])
        self.assertEqual(code, summary['exitCode'])
        self.assertEqual(1, len(summary['attempts']))

    def test_success_requires_nonempty_last_message(self):
        code, summary, output = self.run_fake('ok')
        self.assertEqual(0, code, output)
        self.assertTrue(summary['ok'])

    def test_task_failure_with_artifact_is_not_retried(self):
        code, summary, output = self.run_fake('task-failure')
        self.assertEqual(4, code, output)
        self.assertEqual(1, len(summary['attempts']))
        self.assertFalse(summary['attempts'][0]['retryable'])

    def test_startup_refresh_can_retry_when_no_task_side_effects(self):
        code, summary, output = self.run_fake('refresh')
        self.assertEqual(0, code, output)
        self.assertEqual(2, len(summary['attempts']))

    def test_timeout_is_real_and_not_retried(self):
        code, summary, output = self.run_fake('timeout')
        self.assertEqual(124, code, output)
        self.assertTrue(summary['attempts'][0]['timedOut'])
        self.assertFalse(summary['attempts'][0]['retryable'])
        self.assertFalse(summary['attempts'][0]['artifactsUnchanged'])
        self.assertEqual(1, len(summary['attempts']))

    def test_missing_image_stops_before_launch(self):
        code, summary, output = self.run_fake('ok', ['-Images', 'missing-image.png'])
        self.assertNotEqual(0, code)
        self.assertIsNone(summary)
        self.assertIn('missing-image.png', output)


if __name__ == '__main__':
    unittest.main()
