import json
from typing import Any

from gh_settings_audit.gh import Api, GhApiError, gh_api
from gh_settings_audit.report import CheckResult, Report, Section, Status

# Fields from GET /repos/{owner}/{repo}
EXPECTED_REPO_SETTINGS: dict[str, Any] = {
    "allow_merge_commit": False,
    "squash_merge_commit_title": "PR_TITLE",
    # With squash_merge_commit_title "PR_TITLE", this means "Pull request title" only
    "squash_merge_commit_message": "BLANK",
    "allow_update_branch": True,
    "delete_branch_on_merge": True,
}

# Ruleset rule types that must apply to the default branch, with check names
REQUIRED_RULE_TYPES: dict[str, str] = {
    "non_fast_forward": "no force pushes",
    "required_linear_history": "linear history",
    "pull_request": "require pull requests",
}


def check_repo_settings(repo: dict[str, Any]) -> list[CheckResult]:
    results = []
    for field, expected in EXPECTED_REPO_SETTINGS.items():
        # GitHub returns these fields as null or omits them without admin access
        actual = repo.get(field)
        if actual is None:
            result = CheckResult(Status.UNKNOWN, field, "not visible with your access")
        elif actual == expected:
            result = CheckResult(Status.PASS, field, json.dumps(actual))
        else:
            detail = f"{json.dumps(actual)} (expected {json.dumps(expected)})"
            result = CheckResult(Status.FAIL, field, detail)
        results.append(result)
    return results


def check_branch_rules(rules: list[dict[str, Any]]) -> list[CheckResult]:
    """Check the active rules from GET /repos/{owner}/{repo}/rules/branches/{branch}."""
    if rules:
        count = f"{len(rules)} active rule{'s' if len(rules) != 1 else ''}"
        results = [CheckResult(Status.PASS, "has protection", f"{count} from rulesets")]
    else:
        results = [CheckResult(Status.FAIL, "has protection", "no ruleset rules apply")]
    present = {rule["type"] for rule in rules}
    for rule_type, name in REQUIRED_RULE_TYPES.items():
        if rule_type in present:
            results.append(CheckResult(Status.PASS, name, f"{rule_type} rule present"))
        else:
            results.append(CheckResult(Status.FAIL, name, f"no {rule_type} rule"))
    return results


def check_classic_protection(api: Api, repo: str, branch: str) -> CheckResult:
    name = "classic branch protection"
    try:
        api(f"repos/{repo}/branches/{branch}/protection")
    except GhApiError as e:
        if e.status == 404 and e.message == "Branch not protected":
            return CheckResult(Status.PASS, name, "not used")
        # Reading branch protection needs admin access, and a paid plan for private repos.
        # GitHub responds 403 or 404 without them.
        if e.status in (403, 404):
            return CheckResult(Status.UNKNOWN, name, f"not visible: {e}")
        raise
    return CheckResult(Status.WARN, name, "in use; migrate to rulesets")


def check_default_branch(api: Api, repo: str, branch: str) -> list[CheckResult]:
    try:
        rules = api(f"repos/{repo}/rules/branches/{branch}", paginate=True)
    except GhApiError as e:
        # Rulesets on private repos need a paid plan; GitHub responds 403 without it
        if e.status != 403:
            raise
        names = ["has protection", *REQUIRED_RULE_TYPES.values()]
        rule_results = [CheckResult(Status.UNKNOWN, name, f"not visible: {e}") for name in names]
    else:
        rule_results = check_branch_rules(rules)
    return [*rule_results, check_classic_protection(api, repo, branch)]


def audit(repo: str | None, api: Api = gh_api) -> Report:
    """Audit `repo` (OWNER/REPO), or the current directory's repo if None."""
    repo_data = api(f"repos/{repo}" if repo else "repos/{owner}/{repo}")
    full_name = repo_data["full_name"]
    branch = repo_data["default_branch"]
    return Report(
        repo=full_name,
        default_branch=branch,
        sections=[
            Section("Repo settings", check_repo_settings(repo_data)),
            Section("Default branch rules", check_default_branch(api, full_name, branch)),
        ],
    )
