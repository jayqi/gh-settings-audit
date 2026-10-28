import sys

import pytest

from gh_settings_audit.cli import main
from gh_settings_audit.gh import GhApiError
from tests.helpers import FakeApi, example_repo_api

EXPECTED_REPORT = "\n".join(
    [
        "Repository: jayqi/python-package-reference",
        "Default branch: main",
        "",
        "Repo settings",
        "  ok       allow_merge_commit: false",
        "  ok       allow_squash_merge: true",
        "  ok       allow_rebase_merge: true",
        '  differs  squash_merge_commit_title: "COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")',
        '  differs  squash_merge_commit_message: "COMMIT_MESSAGES" (preferred "BLANK")',
        "  ok       allow_update_branch: true",
        "  ok       delete_branch_on_merge: true",
        "",
        "Default branch rules",
        "  differs  deletion blocked: deletion rule present, "
        'but bypassable (ruleset "Tests Pass": always)',
        "  differs  force pushes blocked: non_fast_forward rule present, "
        'but bypassable (ruleset "Tests Pass": always)',
        "  differs  linear history required: no required_linear_history rule",
        "  differs  pull requests required: no pull_request rule",
        "  differs  status checks required: required_status_checks rule present, "
        'but bypassable (ruleset "Tests Pass": always)',
        "  differs    ↳ branches up to date before merging: depends on status checks required",
        "  differs    ↳ specific status checks listed: depends on status checks required",
        "  differs  classic branch protection: in use; rulesets preferred",
        "",
        "Summary: ok: 5, differs: 10, unknown: 0",
        "",
    ]
)


def test_report_printed_and_exit_zero_despite_differences(capsys):
    assert main(["jayqi/python-package-reference"], api=example_repo_api()) == 0
    assert capsys.readouterr().out == EXPECTED_REPORT


def test_terminal_output_has_colored_symbols(capsys, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert main(["jayqi/python-package-reference"], api=example_repo_api()) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[4] == "  \x1b[32m✓ ok\x1b[0m       allow_merge_commit: false"
    assert lines[7] == (
        "  \x1b[33m~ differs\x1b[0m  squash_merge_commit_title: "
        '"COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")'
    )


def test_terminal_output_respects_no_color(capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert main(["jayqi/python-package-reference"], api=example_repo_api()) == 0
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
