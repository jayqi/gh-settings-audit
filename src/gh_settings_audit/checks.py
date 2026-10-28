import json
from typing import Any
from urllib.parse import quote

from gh_settings_audit.gh import Api, GhApiError, gh_api
from gh_settings_audit.report import CheckResult, Report, Section, Status

# Fields from GET /repos/{owner}/{repo}
PREFERRED_REPO_SETTINGS: dict[str, Any] = {
    "allow_merge_commit": False,
    "allow_squash_merge": True,
    "allow_rebase_merge": True,
    "squash_merge_commit_title": "PR_TITLE",
    # With squash_merge_commit_title "PR_TITLE", this means "Pull request title" only
    "squash_merge_commit_message": "BLANK",
    "allow_update_branch": True,
    "delete_branch_on_merge": True,
}

# Ruleset rule types preferred on the default branch, with check names
PREFERRED_RULE_TYPES: dict[str, str] = {
    "deletion": "deletion blocked",
    "non_fast_forward": "force pushes blocked",
    "required_linear_history": "linear history required",
    "pull_request": "pull requests required",
    "required_status_checks": "status checks required",
}

# Checks of required_status_checks rule parameters, shown under "status checks required"
STATUS_CHECK_SETTINGS = ["branches up to date before merging", "specific status checks listed"]

# Start of the 403 message for rulesets on a private repo without a paid plan
PLAN_UNAVAILABLE_MESSAGE = "Upgrade to GitHub Pro"


def check_repo_settings(repo: dict[str, Any]) -> list[CheckResult]:
    results = []
    for field, preferred in PREFERRED_REPO_SETTINGS.items():
        # GitHub omits these fields without write access
        actual = repo.get(field)
        if actual is None:
            result = CheckResult(Status.UNKNOWN, field, "not visible with your access")
        elif actual == preferred:
            result = CheckResult(Status.OK, field, json.dumps(actual))
        else:
            detail = f"{json.dumps(actual)} (preferred {json.dumps(preferred)})"
            result = CheckResult(Status.DIFFERS, field, detail)
        results.append(result)
    return results


def check_branch_rules(
    rules: list[dict[str, Any]], rulesets: dict[int, dict[str, Any]]
) -> list[CheckResult]:
    """Check the active rules from GET /repos/{owner}/{repo}/rules/branches/{branch}.

    `rulesets` maps ruleset IDs to GET /repos/{owner}/{repo}/rulesets/{id} responses.
    A rule counts only if at least one ruleset providing it has no bypass actors.
    """
    results = []
    for rule_type, name in PREFERRED_RULE_TYPES.items():
        providers = [
            (rule, rulesets[rule["ruleset_id"]]) for rule in rules if rule["type"] == rule_type
        ]
        enforced = [rule for rule, ruleset in providers if ruleset.get("bypass_actors") == []]
        if not providers:
            result = CheckResult(Status.DIFFERS, name, f"no {rule_type} rule")
        elif enforced:
            result = CheckResult(Status.OK, name, f"{rule_type} rule present")
        # GitHub omits bypass_actors without admin access
        elif any(ruleset.get("bypass_actors") is None for _, ruleset in providers):
            detail = f"{rule_type} rule present; bypass list not visible"
            result = CheckResult(Status.UNKNOWN, name, detail)
        else:
            bypasses = "; ".join(
                f'ruleset "{ruleset["name"]}": '
                + ", ".join(sorted({actor["bypass_mode"] for actor in ruleset["bypass_actors"]}))
                for _, ruleset in providers
            )
            detail = f"{rule_type} rule present, but bypassable ({bypasses})"
            result = CheckResult(Status.DIFFERS, name, detail)
        results.append(result)
        if rule_type == "required_status_checks":
            results += check_status_check_settings(result, enforced)
    return results


def check_status_check_settings(
    parent: CheckResult, enforced: list[dict[str, Any]]
) -> list[CheckResult]:
    """Check the parameters of enforced required_status_checks rules, under `parent`."""
    strict_name, listed_name = STATUS_CHECK_SETTINGS
    if parent.status != Status.OK:
        detail = f"depends on {parent.name}"
        return [
            CheckResult(parent.status, name, detail, child=True) for name in STATUS_CHECK_SETTINGS
        ]

    if any(rule["parameters"]["strict_required_status_checks_policy"] for rule in enforced):
        strict = CheckResult(Status.OK, strict_name, "strict policy set", child=True)
    else:
        strict = CheckResult(Status.DIFFERS, strict_name, "strict policy not set", child=True)

    contexts = sorted(
        {
            check["context"]
            for rule in enforced
            for check in rule["parameters"]["required_status_checks"]
        }
    )
    if contexts:
        count = f"{len(contexts)} check{'s' if len(contexts) != 1 else ''}"
        detail = f"{count} ({', '.join(contexts)})"
        listed = CheckResult(Status.OK, listed_name, detail, child=True)
    else:
        listed = CheckResult(Status.DIFFERS, listed_name, "no checks listed", child=True)
    return [strict, listed]


def check_classic_protection(branch: dict[str, Any]) -> CheckResult:
    """Check a GET /repos/{owner}/{repo}/branches/{branch} response."""
    name = "classic branch protection"
    if branch["protection"]["enabled"]:
        return CheckResult(Status.DIFFERS, name, "in use; rulesets preferred")
    return CheckResult(Status.OK, name, "not used")


def check_default_branch(api: Api, repo: str, branch: str) -> list[CheckResult]:
    branch_path = quote(branch, safe="/")
    try:
        rules = api(f"repos/{repo}/rules/branches/{branch_path}", paginate=True)
    except GhApiError as e:
        if not (e.status == 403 and e.message.startswith(PLAN_UNAVAILABLE_MESSAGE)):
            raise
        detail = "rulesets not available on this repo's plan"
        results = [
            CheckResult(Status.DIFFERS, name, detail) for name in PREFERRED_RULE_TYPES.values()
        ]
        results += [
            CheckResult(Status.DIFFERS, name, detail, child=True) for name in STATUS_CHECK_SETTINGS
        ]
    else:
        ruleset_ids = sorted(
            {rule["ruleset_id"] for rule in rules if rule["type"] in PREFERRED_RULE_TYPES}
        )
        rulesets = {id_: api(f"repos/{repo}/rulesets/{id_}") for id_ in ruleset_ids}
        results = check_branch_rules(rules, rulesets)

    try:
        branch_data = api(f"repos/{repo}/branches/{branch_path}")
    except GhApiError as e:
        # The default branch doesn't exist yet in an empty repo
        if e.status != 404:
            raise
        results.append(CheckResult(Status.UNKNOWN, "classic branch protection", str(e)))
    else:
        results.append(check_classic_protection(branch_data))
    return results


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
