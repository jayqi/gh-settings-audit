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
from tests.helpers import FakeApi, example_repo_api, load_fixture


def statuses(results: list[CheckResult]) -> dict[str, Status]:
    return {result.name: result.status for result in results}


def details(results: list[CheckResult]) -> dict[str, str]:
    return {result.name: result.detail for result in results}


## Repo settings


def test_repo_settings_all_match():
    repo = load_fixture("repo_admin.json") | PREFERRED_REPO_SETTINGS
    assert statuses(check_repo_settings(repo)) == {
        "allow_merge_commit": Status.OK,
        "allow_squash_merge": Status.OK,
        "allow_rebase_merge": Status.OK,
        "squash_merge_commit_title": Status.OK,
        "squash_merge_commit_message": Status.OK,
        "allow_update_branch": Status.OK,
        "delete_branch_on_merge": Status.OK,
    }


def test_repo_settings_mismatches_differ():
    assert statuses(check_repo_settings(load_fixture("repo_admin.json"))) == {
        "allow_merge_commit": Status.OK,
        "allow_squash_merge": Status.OK,
        "allow_rebase_merge": Status.OK,
        "squash_merge_commit_title": Status.DIFFERS,
        "squash_merge_commit_message": Status.DIFFERS,
        "allow_update_branch": Status.OK,
        "delete_branch_on_merge": Status.OK,
    }


def test_repo_settings_mismatch_shows_actual_and_preferred():
    results = details(check_repo_settings(load_fixture("repo_admin.json")))
    assert results["squash_merge_commit_title"] == '"COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")'


def test_repo_settings_omitted_without_access_are_unknown():
    results = check_repo_settings(load_fixture("repo_no_admin.json"))
    assert {(r.status, r.detail) for r in results} == {
        (Status.UNKNOWN, "not visible with your access")
    }


## Default-branch rules


def test_branch_rules_present_without_bypass():
    results = check_branch_rules(
        load_fixture("rules_no_bypass.json"), {25855599: load_fixture("ruleset_no_bypass.json")}
    )
    assert statuses(results) == {
        "deletion blocked": Status.OK,
        "force pushes blocked": Status.OK,
        "linear history required": Status.OK,
        "pull requests required": Status.OK,
    }


def test_branch_rules_bypassable_or_missing_differ():
    results = check_branch_rules(
        load_fixture("rules_partial.json"), {24132521: load_fixture("ruleset_bypass_always.json")}
    )
    assert statuses(results) == {
        "deletion blocked": Status.DIFFERS,
        "force pushes blocked": Status.DIFFERS,
        "linear history required": Status.DIFFERS,
        "pull requests required": Status.DIFFERS,
    }
    assert details(results) == {
        "deletion blocked": 'deletion rule present, but bypassable (ruleset "Tests Pass": always)',
        "force pushes blocked": (
            'non_fast_forward rule present, but bypassable (ruleset "Tests Pass": always)'
        ),
        "linear history required": "no required_linear_history rule",
        "pull requests required": "no pull_request rule",
    }


def test_branch_rule_is_ok_if_any_providing_ruleset_has_no_bypass():
    rules = load_fixture("rules_partial.json") + load_fixture("rules_no_bypass.json")
    rulesets = {
        24132521: load_fixture("ruleset_bypass_always.json"),
        25855599: load_fixture("ruleset_no_bypass.json"),
    }
    assert statuses(check_branch_rules(rules, rulesets))["force pushes blocked"] == Status.OK


def test_branch_rules_with_hidden_bypass_list_are_unknown():
    results = check_branch_rules(
        load_fixture("rules_all_required.json"),
        {14390474: load_fixture("ruleset_bypass_hidden.json")},
    )
    assert {(r.status, r.detail) for r in results} == {
        (Status.UNKNOWN, "deletion rule present; bypass list not visible"),
        (Status.UNKNOWN, "non_fast_forward rule present; bypass list not visible"),
        (Status.UNKNOWN, "required_linear_history rule present; bypass list not visible"),
        (Status.UNKNOWN, "pull_request rule present; bypass list not visible"),
    }


def test_branch_rules_none():
    assert set(statuses(check_branch_rules(load_fixture("rules_none.json"), {})).values()) == {
        Status.DIFFERS
    }


## Classic branch protection


def test_classic_protection_enabled_differs():
    assert check_classic_protection(load_fixture("branch_classic.json")).status == Status.DIFFERS


@pytest.mark.parametrize("fixture", ["branch_rulesets_only.json", "branch_unprotected.json"])
def test_classic_protection_not_enabled_is_ok(fixture):
    assert check_classic_protection(load_fixture(fixture)).status == Status.OK


## Full audit


def test_audit_named_repo():
    api = example_repo_api()
    report = audit("jayqi/python-package-reference", api=api)

    assert report.repo == "jayqi/python-package-reference"
    assert report.default_branch == "main"
    assert [section.title for section in report.sections] == [
        "Repo settings",
        "Default branch rules",
    ]
    assert [r.name for r in report.sections[1].results] == [
        "deletion blocked",
        "force pushes blocked",
        "linear history required",
        "pull requests required",
        "classic branch protection",
    ]
    assert api.calls == [
        ("repos/jayqi/python-package-reference", False),
        ("repos/jayqi/python-package-reference/rules/branches/main", True),
        ("repos/jayqi/python-package-reference/rulesets/24132521", False),
        ("repos/jayqi/python-package-reference/branches/main", False),
    ]


def test_audit_current_repo_uses_gh_placeholders():
    api = example_repo_api("repos/{owner}/{repo}")
    report = audit(None, api=api)

    assert report.repo == "jayqi/python-package-reference"
    assert api.calls[0] == ("repos/{owner}/{repo}", False)


def test_audit_encodes_branch_name():
    api = FakeApi(
        {
            "repos/o/r": {"full_name": "o/r", "default_branch": "dev/a#b"},
            "repos/o/r/rules/branches/dev/a%23b": [],
            "repos/o/r/branches/dev/a%23b": load_fixture("branch_unprotected.json"),
        }
    )
    assert audit("o/r", api=api).default_branch == "dev/a#b"


def test_audit_rulesets_unavailable_on_plan_differ():
    body = load_fixture("rules_plan_unavailable.json")
    api = example_repo_api()
    api.responses["repos/jayqi/python-package-reference/rules/branches/main"] = GhApiError(
        403, body["message"]
    )
    report = audit("jayqi/python-package-reference", api=api)

    assert {(r.name, r.status, r.detail) for r in report.sections[1].results[:4]} == {
        ("deletion blocked", Status.DIFFERS, "rulesets not available on this repo's plan"),
        ("force pushes blocked", Status.DIFFERS, "rulesets not available on this repo's plan"),
        ("linear history required", Status.DIFFERS, "rulesets not available on this repo's plan"),
        ("pull requests required", Status.DIFFERS, "rulesets not available on this repo's plan"),
    }


def test_audit_propagates_other_rules_errors():
    api = example_repo_api()
    api.responses["repos/jayqi/python-package-reference/rules/branches/main"] = GhApiError(
        403, "API rate limit exceeded for user ID 1."
    )
    with pytest.raises(GhApiError):
        audit("jayqi/python-package-reference", api=api)


def test_audit_missing_default_branch_is_unknown():
    body = load_fixture("branch_not_found.json")
    api = example_repo_api()
    api.responses["repos/jayqi/python-package-reference/rules/branches/main"] = []
    api.responses["repos/jayqi/python-package-reference/branches/main"] = GhApiError(
        404, body["message"]
    )
    report = audit("jayqi/python-package-reference", api=api)

    classic = report.sections[1].results[-1]
    assert (classic.status, classic.detail) == (Status.UNKNOWN, "Branch not found (HTTP 404)")


def test_audit_propagates_other_branch_errors():
    api = example_repo_api()
    api.responses["repos/jayqi/python-package-reference/branches/main"] = GhApiError(
        500, "Server Error"
    )
    with pytest.raises(GhApiError):
        audit("jayqi/python-package-reference", api=api)


def test_audit_propagates_api_errors():
    api = FakeApi({"repos/o/missing": GhApiError(404, "Not Found")})
    with pytest.raises(GhApiError):
        audit("o/missing", api=api)
