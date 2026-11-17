"""Native subprocess/negative controls, not live model or rendered-review proof."""
import copy
import json
import subprocess
import sys
import shlex
import unittest
import test_design_evidence as fixture
from test_design_evidence import evidence, HELPER


class DesignHandoffTests(unittest.TestCase):
    write = fixture.DesignEvidenceTests.write
    review = fixture.DesignEvidenceTests.review
    package = fixture.DesignEvidenceTests.package
    def setUp(self):
        fixture.DesignEvidenceTests.setUp(self)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        self.profile['checks'] = {'native': [sys.executable, '-c', 'print("native executed")']}
        self.write(self.root / evidence.PROFILE, self.profile)
        self.checks_dir = self.base / 'checks'
        self.record_path = self.base / 'review-record.json'

    def ready(self):
        evidence.run_checks(self.root, self.checks_dir)
        self.brief["checks"] = [{"command": shlex.join(self.profile["checks"]["native"]),
                                  "evidence": "checks/native-1.log"}]
        self.review()
        record = {'packetFingerprint': evidence.read_json(self.packet / 'packet.json')['fingerprint'],
                  'reviewSha256': evidence.digest(self.review_path.read_bytes()),
                  'authorSession': 'synthetic-author', 'reviewerSession': 'synthetic-reviewer'}
        for key in ['firstLookNotes', 'transcript']:
            p = self.base / (key + '.txt')
            p.write_text('Synthetic fixture; not actual independent review')
            record[key] = {'path': p.name, 'sha256': evidence.digest(p.read_bytes())}
        self.write(self.record_path, record)

    def gate(self):
        return evidence.handoff(self.root, self.packet, self.review_path, self.checks_dir, self.record_path)

    def test_fresh_process_reads_persistent_project_evidence(self):
        self.ready()
        argv = [sys.executable, str(HELPER), '--repo', str(self.root), 'handoff',
                '--packet', str(self.packet), '--review', str(self.review_path),
                '--checks', str(self.checks_dir), '--review-record', str(self.record_path)]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'HANDOFF_EVIDENCE_COMPLETE')
        self.assertTrue(json.loads(result.stdout)['advisory'])
        (self.root / 'src/ui.ts').write_text('later thread changed source')
        self.assertNotEqual(subprocess.run(argv, capture_output=True).returncode, 0)

    def test_silent_native_success_completes_handoff(self):
        self.profile['checks']['native'] = [sys.executable, '-c', 'pass']
        self.write(self.root / evidence.PROFILE, self.profile)
        self.ready()
        log = (self.checks_dir / 'native-1.log').read_bytes()
        header, output = log.split(b'\n', 1)
        self.assertEqual(json.loads(header), {'argv': self.profile['checks']['native'],
                         'exitCode': 0, 'stdoutBytes': 0, 'stderrBytes': 0})
        self.assertEqual(output, b'stdout:\n\nstderr:\n')
        self.assertEqual(self.gate()['status'], 'HANDOFF_EVIDENCE_COMPLETE')
        (self.checks_dir / 'native-1.log').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Native log changed'):
            self.gate()
        (self.checks_dir / 'native-1.log').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing project path'):
            self.gate()

    def test_native_log_preserves_both_output_streams(self):
        self.profile['checks']['native'] = [sys.executable, '-c',
            'import os; os.write(1, b"out\\xff"); os.write(2, b"err\\xfe")']
        self.write(self.root / evidence.PROFILE, self.profile)
        evidence.run_checks(self.root, self.checks_dir)
        header, output = (self.checks_dir / 'native-1.log').read_bytes().split(b'\n', 1)
        self.assertEqual(json.loads(header), {'argv': self.profile['checks']['native'],
                         'exitCode': 0, 'stdoutBytes': 4, 'stderrBytes': 4})
        self.assertEqual(output, b'stdout:\nout\xff\nstderr:\nerr\xfe')

    def test_native_failure_retained(self):
        self.profile['checks']['native'] = [sys.executable, '-c', 'raise SystemExit(3)']
        self.write(self.root / evidence.PROFILE, self.profile)
        with self.assertRaisesRegex(ValueError, 'Native checks failed'):
            evidence.run_checks(self.root, self.checks_dir)
        self.assertEqual(evidence.read_json(self.checks_dir / 'receipt.json')['checks'][0]['exitCode'], 3)

    def test_native_source_mutation_rejected(self):
        self.profile['checks']['native'] = [sys.executable, '-c', 'open("src/ui.ts","w").write("changed")']
        self.write(self.root / evidence.PROFILE, self.profile)
        with self.assertRaisesRegex(ValueError, 'changed reviewed source'):
            evidence.run_checks(self.root, self.checks_dir)

    def test_missing_review_record_fails(self):
        self.ready()
        self.record_path.unlink()
        with self.assertRaises(OSError): self.gate()

    def test_author_cannot_supply_same_session(self):
        self.ready()
        record = evidence.read_json(self.record_path)
        record['reviewerSession'] = record['authorSession']
        self.write(self.record_path, record)
        with self.assertRaisesRegex(ValueError, 'Author cannot'): self.gate()

    def test_changed_notes_response_and_transcript_rejected(self):
        self.ready()
        for p in [self.base / 'firstLookNotes.txt', self.base / 'transcript.txt']:
            before = p.read_bytes(); p.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed reviewer evidence'): self.gate()
            p.write_bytes(before)
        review = evidence.read_json(self.review_path)
        review['reviewer'] = 'another name'
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, 'response changed'): self.gate()

    def test_missing_failed_command_or_tampered_native_receipt(self):
        self.ready()
        path = self.checks_dir / 'receipt.json'
        original = evidence.read_json(path)
        for change in ['missing', 'argv', 'failed']:
            receipt = copy.deepcopy(original)
            if change == 'missing': receipt['checks'] = []
            if change == 'argv': receipt['checks'][0]['argv'] = ['true']
            if change == 'failed': receipt['checks'][0]['exitCode'] = 1
            self.write(path, receipt)
            with self.assertRaises(ValueError): self.gate()
        self.write(path, original)
        (self.checks_dir / 'native-1.log').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Native log changed'): self.gate()

    def test_same_files_new_git_revision_invalidates_packet(self):
        self.ready()
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'later'], check=True)
        with self.assertRaisesRegex(ValueError, 'stale'): self.gate()
        new_dir = self.base / 'new-checks'
        evidence.run_checks(self.root, new_dir)
        self.checks_dir = new_dir
        with self.assertRaisesRegex(ValueError, 'Packet Git revision is stale'): self.gate()

    def test_findings_fail_handoff(self):
        self.ready()
        review = evidence.read_json(self.review_path)
        review['questions'] = ['Unresolved scope']
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, 'not complete'): self.gate()

    def test_deleted_source_still_retains_failed_receipt(self):
        self.profile['checks']['native'] = [sys.executable, '-c', 'import os; os.unlink("contract.md"); raise SystemExit(3)']
        self.write(self.root / evidence.PROFILE, self.profile)
        with self.assertRaisesRegex(ValueError, 'changed reviewed source'):
            evidence.run_checks(self.root, self.checks_dir)
        receipt = evidence.read_json(self.checks_dir / 'receipt.json')
        self.assertFalse(receipt['sourceUnchanged'])
        self.assertEqual(receipt['checks'][0]['exitCode'], 3)

    def test_unrelated_packet_logs_fail(self):
        self.ready()
        packet = evidence.read_json(self.packet / 'packet.json')
        packet['checks'][0]['command'] = 'unrelated command'
        packet.pop('fingerprint')
        packet['fingerprint'] = evidence.digest(evidence.encode(packet))
        self.write(self.packet / 'packet.json', packet)
        for name, value in evidence.review_inputs(packet).items():
            p = self.packet / name
            p.write_text(value) if isinstance(value, str) else self.write(p, value)
        review = evidence.read_json(self.review_path)
        review['packetFingerprint'] = packet['fingerprint']
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, 'exact native command logs'):
            self.gate()

    def test_scratch_proposal_without_git_binds_exact_source(self):
        import shutil
        shutil.rmtree(self.root / '.git')
        self.ready()
        result = self.gate()
        self.assertIsNone(result['head'])
        self.assertEqual(len(result['sourceFingerprint']), 64)
        (self.root / 'src/ui.ts').write_text('revised proposal')
        with self.assertRaisesRegex(ValueError, 'Project source changed'):
            self.gate()
