import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request, urlopen

from scripts import check_certification_ci as diagnostic


class RuntimeDiagnosticsTest(unittest.TestCase):
    def test_resource_report_excludes_process_details(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / 'self').mkdir()
            (proc / 'self/status').write_text('Name:\tprivate-command\nVmRSS:\t42 kB\n')
            (proc / 'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 700 kB\n')
            (proc / '123').mkdir()
            self.assertEqual(diagnostic.resource_snapshot(proc), {
                'memory_total_kib': 1000, 'memory_available_kib': 700,
                'harness_rss_kib': 42, 'process_count': 1})
            self.assertEqual(diagnostic.resource_snapshot(proc / 'absent'), {
                'memory_total_kib': None, 'memory_available_kib': None,
                'harness_rss_kib': None, 'process_count': None})

    def test_task_bound_rejected_before_any_setup(self):
        for count in (0, -1, 92):
            with self.subTest(count=count), self.assertRaisesRegex(RuntimeError, 'between 1 and 91'):
                diagnostic.check(argparse.Namespace(tasks=count))

    def test_synthetic_provider_repeats_tool_then_final_for_each_task(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state.json'
            script = Path(diagnostic.__file__)
            with subprocess.Popen([sys.executable, '-I', str(script), 'serve', '--state', str(state)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
                try:
                    subprocess.run([sys.executable, '-I', str(script), 'ready', '--state', str(state)],
                                   check=True, capture_output=True, timeout=15)
                    port = json.loads(state.read_text())['port']
                    for index in range(4):
                        body = {'model': diagnostic.certification.MODEL, 'reasoning': {'effort': 'medium'},
                                'input': [{'type': 'custom_tool_call_output',
                                           'output': 'Synthetic fixture instructions'}] if index % 2 else []}
                        request = Request(f'http://127.0.0.1:{port}/v1/responses',
                                          data=json.dumps(body).encode(), headers={
                                              'Authorization': 'Bearer ' + diagnostic.FAKE_CREDENTIAL,
                                              'Content-Type': 'application/json'})
                        with urlopen(request, timeout=5) as response:
                            events = [json.loads(line[6:]) for line in response.read().decode().splitlines()
                                      if line.startswith('data: ')]
                        item = events[-1]['response']['output'][0]
                        self.assertEqual(item['type'], 'custom_tool_call' if index % 2 == 0 else 'message')
                    observed = json.loads(state.read_text())
                    self.assertEqual(len(observed['requests']), 4)
                    self.assertEqual(observed['tool_read_count'], 2)
                    self.assertTrue(all(all(request.values()) for request in observed['requests']))
                finally:
                    process.terminate()
                    process.wait(timeout=5)
