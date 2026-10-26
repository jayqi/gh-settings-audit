import pytest

from gh_settings_audit.checks import (
    PREFERRED_REPO_SETTINGS,
    audit,
    check_branch_rules,
    check_classic_protection,
    check_repo_settings,
)
from gh_settings_audit.gh import GhApiError
from gh_settings_audit.report import CheckResult, Status
from tests.helpers import FakeApi, load_fixture


def statuses(results: list[CheckResult]) -> dict[str, Status]:
    return {result.name: result.status for result in results}


## Repo settings


def test_repo_settings_all_match():
    repo = load_fixture("repo_admin.json") | PREFERRED_REPO_SETTINGS
    assert statuses(check_repo_settings(repo)) == {
        "allow_merge_commit": Status.OK,
        "squash_merge_commit_title": Status.OK,
        "squash_merge_commit_message": Status.OK,
        "allow_update_branch": Status.OK,
        "delete_branch_on_merge": Status.OK,
    }


def test_repo_settings_mismatches_differ():
    assert statuses(check_repo_settings(load_fixture("repo_admin.json"))) == {
        "allow_merge_commit": Status.OK,
        "squash_merge_commit_title": Status.DIFFERS,
        "squash_merge_commit_message": Status.DIFFERS,
        "allow_update_branch": Status.OK,
        "delete_branch_on_merge": Status.OK,
    }


def test_repo_settings_mismatch_shows_actual_and_preferred():
    results = check_repo_settings(load_fixture("repo_admin.json"))
    title = next(r for r in results if r.name == "squash_merge_commit_title")
    assert title.detail == '"COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")'


def test_repo_settings_hidden_without_admin_are_unknown():
    results = check_repo_settings(load_fixture("repo_no_admin.json"))
    assert set(statuses(results).values()) == {Status.UNKNOWN}


## Default-branch rules


def test_branch_rules_all_required_present():
    assert statuses(check_branch_rules(load_fixture("rules_all_required.json"))) == {
        "has protection": Status.OK,
        "no force pushes": Status.OK,
        "linear history": Status.OK,
        "require pull requests": Status.OK,
    }


def test_branch_rules_partial():
    assert statuses(check_branch_rules(load_fixture("rules_partial.json"))) == {
        "has protection": Status.OK,
        "no force pushes": Status.OK,
        "linear history": Status.DIFFERS,
        "require pull requests": Status.DIFFERS,
    }


def test_branch_rules_none():
    assert statuses(check_branch_rules(load_fixture("rules_none.json"))) == {
        "has protection": Status.DIFFERS,
        "no force pushes": Status.DIFFERS,
        "linear history": Status.DIFFERS,
        "require pull requests": Status.DIFFERS,
    }


## Classic branch protection

PROTECTION_ENDPOINT = "repos/o/r/branches/main/protection"


def test_classic_protection_present_differs():
    api = FakeApi({PROTECTION_ENDPOINT: load_fixture("protection_present.json")})
    assert check_classic_protection(api, "o/r", "main").status == Status.DIFFERS


def test_classic_protection_absent_is_ok():
    api = FakeApi({PROTECTION_ENDPOINT: GhApiError(404, "Branch not protected")})
    assert check_classic_protection(api, "o/r", "main").status == Status.OK


@pytest.mark.parametrize(
    "error",
    [GhApiError(404, "Not Found"), GhApiError(403, "Resource not accessible by integration")],
)
def test_classic_protection_without_access_is_unknown(error):
    api = FakeApi({PROTECTION_ENDPOINT: error})
    assert check_classic_protection(api, "o/r", "main").status == Status.UNKNOWN


def test_classic_protection_other_errors_propagate():
    api = FakeApi({PROTECTION_ENDPOINT: GhApiError(500, "Server Error")})
    with pytest.raises(GhApiError):
        check_classic_protection(api, "o/r", "main")


## Full audit


def admin_repo_api(repo_endpoint: str) -> FakeApi:
    return FakeApi(
        {
            repo_endpoint: load_fixture("repo_admin.json"),
            "repos/jayqi/python-package-reference/rules/branches/main": load_fixture(
                "rules_partial.json"
            ),
            "repos/jayqi/python-package-reference/branches/main/protection": load_fixture(
                "protection_present.json"
            ),
        }
    )


def test_audit_named_repo():
    api = admin_repo_api("repos/jayqi/python-package-reference")
    report = audit("jayqi/python-package-reference", api=api)

    assert report.repo == "jayqi/python-package-reference"
    assert report.default_branch == "main"
    assert [section.title for section in report.sections] == [
        "Repo settings",
        "Default branch rules",
    ]
    assert [r.name for r in report.sections[1].results] == [
        "has protection",
        "no force pushes",
        "linear history",
        "require pull requests",
        "classic branch protection",
    ]


def test_audit_current_repo_uses_gh_placeholders():
    api = admin_repo_api("repos/{owner}/{repo}")
    report = audit(None, api=api)

    assert report.repo == "jayqi/python-package-reference"
    assert api.calls == [
        "repos/{owner}/{repo}",
        "repos/jayqi/python-package-reference/rules/branches/main",
        "repos/jayqi/python-package-reference/branches/main/protection",
    ]


def test_audit_rules_forbidden_are_unknown():
    body = load_fixture("rules_plan_unavailable.json")
    api = admin_repo_api("repos/jayqi/python-package-reference")
    api.responses["repos/jayqi/python-package-reference/rules/branches/main"] = GhApiError(
        403, body["message"]
    )
    report = audit("jayqi/python-package-reference", api=api)

    assert statuses(report.sections[1].results) == {
        "has protection": Status.UNKNOWN,
        "no force pushes": Status.UNKNOWN,
        "linear history": Status.UNKNOWN,
        "require pull requests": Status.UNKNOWN,
        "classic branch protection": Status.DIFFERS,
    }


def test_audit_propagates_api_errors():
    api = FakeApi({"repos/o/missing": GhApiError(404, "Not Found")})
    with pytest.raises(GhApiError):
        audit("o/missing", api=api)


def test_audit_propagates_other_rules_errors():
    api = admin_repo_api("repos/jayqi/python-package-reference")
    api.responses["repos/jayqi/python-package-reference/rules/branches/main"] = GhApiError(
        500, "Server Error"
    )
    with pytest.raises(GhApiError):
        audit("jayqi/python-package-reference", api=api)
