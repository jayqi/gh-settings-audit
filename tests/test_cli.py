import sys

import pytest

from gh_settings_audit.cli import main
from gh_settings_audit.gh import GhApiError
from tests.helpers import FakeApi, load_fixture

EXPECTED_REPORT = """\
Repository: jayqi/python-package-reference
Default branch: main

Repo settings
  ok       allow_merge_commit: false
  differs  squash_merge_commit_title: "COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")
  differs  squash_merge_commit_message: "COMMIT_MESSAGES" (preferred "BLANK")
  ok       allow_update_branch: true
  ok       delete_branch_on_merge: true

Default branch rules
  ok       has protection: 3 active rules from rulesets
  ok       no force pushes: non_fast_forward rule present
  differs  linear history: no required_linear_history rule
  differs  require pull requests: no pull_request rule
  differs  classic branch protection: in use; rulesets preferred

Summary: ok: 5, differs: 5, unknown: 0
"""


def admin_repo_api() -> FakeApi:
    return FakeApi(
        {
            "repos/jayqi/python-package-reference": load_fixture("repo_admin.json"),
            "repos/jayqi/python-package-reference/rules/branches/main": load_fixture(
                "rules_partial.json"
            ),
            "repos/jayqi/python-package-reference/branches/main/protection": load_fixture(
                "protection_present.json"
            ),
        }
    )


def test_report_printed_and_exit_zero_despite_differences(capsys):
    assert main(["jayqi/python-package-reference"], api=admin_repo_api()) == 0
    assert capsys.readouterr().out == EXPECTED_REPORT


def test_terminal_output_has_colored_symbols(capsys, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert main(["jayqi/python-package-reference"], api=admin_repo_api()) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[4] == "  \x1b[32m✓ ok\x1b[0m       allow_merge_commit: false"
    assert lines[5] == (
        "  \x1b[33m~ differs\x1b[0m  squash_merge_commit_title: "
        '"COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")'
    )


def test_terminal_output_respects_no_color(capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert main(["jayqi/python-package-reference"], api=admin_repo_api()) == 0
    assert capsys.readouterr().out == EXPECTED_REPORT


def test_api_error_exits_nonzero(capsys):
    api = FakeApi({"repos/o/missing": GhApiError(404, "Not Found")})

    assert main(["o/missing"], api=api) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "gh-settings-audit: error: Not Found (HTTP 404)\n"


@pytest.mark.parametrize("arg", ["o", "o/r/x", "https://github.com/o/r"])
def test_invalid_repo_argument(arg, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([arg], api=FakeApi({}))
    assert exc_info.value.code == 2
    assert "OWNER/REPO" in capsys.readouterr().err
