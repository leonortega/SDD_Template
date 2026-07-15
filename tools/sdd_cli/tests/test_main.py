"""Tests for __main__.py — CLI entry point module."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tools.sdd_cli import cli


class MainModuleTests(unittest.TestCase):
    """Test the __main__.py entry point behavior."""

    def test_main_with_no_args_returns_1(self) -> None:
        """main() with no args should return exit code 1."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = cli.main([])
        self.assertEqual(1, rc)
        self.assertIn("environment-lab", stderr.getvalue())

    def test_main_with_prereqs_check(self) -> None:
        """main() with prereqs check should run without crashing."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cli.main(["prereqs", "check"])
        self.assertEqual(0, rc)
        self.assertIn("python", stdout.getvalue())

    def test_main_with_invalid_command(self) -> None:
        """main() with an invalid subcommand raises SystemExit from argparse."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                cli.main(["nonexistent-command"])


if __name__ == "__main__":
    unittest.main()
