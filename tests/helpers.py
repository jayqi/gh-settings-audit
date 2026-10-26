import json
from pathlib import Path
from typing import Any

from gh_settings_audit.gh import GhApiError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text())


class FakeApi:
    """Stands in for gh_api, serving canned responses keyed by endpoint."""

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, bool]] = []

    def __call__(self, endpoint: str, paginate: bool = False) -> Any:
        self.calls.append((endpoint, paginate))
        response = self.responses[endpoint]
        if isinstance(response, GhApiError):
            raise response
        return response


def example_repo_api(repo_endpoint: str = "repos/jayqi/python-package-reference") -> FakeApi:
    """jayqi/python-package-reference with a bypassable ruleset and classic protection."""
    return FakeApi(
        {
            repo_endpoint: load_fixture("repo_admin.json"),
            "repos/jayqi/python-package-reference/rules/branches/main": load_fixture(
                "rules_partial.json"
            ),
            "repos/jayqi/python-package-reference/rulesets/24132521": load_fixture(
                "ruleset_bypass_always.json"
            ),
            "repos/jayqi/python-package-reference/branches/main": load_fixture(
                "branch_classic.json"
            ),
        }
    )
