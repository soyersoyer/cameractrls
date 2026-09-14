#!/usr/bin/env python3

import subprocess
import unittest
from unittest.mock import patch

import cameractrls


class ExecAndGetLinesTest(unittest.TestCase):
    @patch('cameractrls.subprocess.run')
    def test_returns_output_lines_with_a_bounded_probe(self, run):
        run.return_value.stdout = b'first\nsecond\n'

        self.assertEqual(
            [b'first', b'second'],
            cameractrls.exec_and_get_lines(['/helper', '-l']),
        )
        run.assert_called_once_with(
            ['/helper', '-l'],
            capture_output=True,
            timeout=cameractrls.ptz_helper_timeout,
        )

    @patch('cameractrls.subprocess.run')
    def test_skips_a_probe_that_times_out(self, run):
        run.side_effect = subprocess.TimeoutExpired(['/helper', '-l'], 5)

        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual([], cameractrls.exec_and_get_lines(['/helper', '-l']))

        self.assertIn('/helper timed out, skipping', logs.output[0])


if __name__ == '__main__':
    unittest.main()
