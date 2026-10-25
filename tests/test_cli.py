import pytest

from gh_settings_audit.cli import main
from gh_settings_audit.gh import GhApiError
from tests.helpers import FakeApi, load_fixture

EXPECTED_REPORT = """\
Repository: jayqi/python-package-reference
Default branch: main

Repo settings
  PASS     allow_merge_commit: false
  FAIL     squash_merge_commit_title: "COMMIT_OR_PR_TITLE" (expected "PR_TITLE")
  FAIL     squash_merge_commit_message: "COMMIT_MESSAGES" (expected "BLANK")
  PASS     allow_update_branch: true
  PASS     delete_branch_on_merge: true

Default branch rules
  PASS     has protection: 3 active rules from rulesets
  PASS     no force pushes: non_fast_forward rule present
  FAIL     linear history: no required_linear_history rule
  FAIL     require pull requests: no pull_request rule
  WARN     classic branch protection: in use; migrate to rulesets

Summary: 5 PASS, 4 FAIL, 1 WARN, 0 UNKNOWN
"""


def test_report_printed_and_exit_zero_despite_failures(capsys):
    api = FakeApi(
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

    assert main(["jayqi/python-package-reference"], api=api) == 0
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
