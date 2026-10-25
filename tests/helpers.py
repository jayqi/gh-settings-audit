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
        self.calls: list[str] = []

    def __call__(self, endpoint: str, paginate: bool = False) -> Any:
        self.calls.append(endpoint)
        response = self.responses[endpoint]
        if isinstance(response, GhApiError):
            raise response
        return response
