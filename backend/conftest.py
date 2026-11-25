"""
Root conftest.py for the FinPilot AI backend test suite.

Django's test-DB creation prompts "Destroy existing test database?" via
input() when a stale test DB is found, which blocks non-interactive runs
(CI, Kiro tool sandbox). Patch input() to auto-answer "yes".
"""
import builtins


def pytest_configure(config):
    _real_input = builtins.input

    def _auto_yes(prompt=""):
        # answer the destroy prompt; any other stray prompt just returns yes too
        return "yes"

    builtins.input = _auto_yes
