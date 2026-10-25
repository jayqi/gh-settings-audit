import json
import subprocess

import pytest

from gh_settings_audit import gh
from gh_settings_audit.gh import GhApiError, gh_api
from tests.helpers import FIXTURES_DIR, load_fixture


def fake_run(stdout: str, returncode: int = 0, stderr: str = ""):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    run.calls = calls
    return run


def test_returns_parsed_json(monkeypatch):
    body = (FIXTURES_DIR / "repo_admin.json").read_text()
    run = fake_run(body)
    monkeypatch.setattr(gh.subprocess, "run", run)

    assert gh_api("repos/jayqi/python-package-reference") == json.loads(body)
    assert run.calls == [["gh", "api", "repos/jayqi/python-package-reference"]]


def test_paginate_flattens_pages(monkeypatch):
    run = fake_run(json.dumps([[{"type": "deletion"}], [{"type": "pull_request"}]]))
    monkeypatch.setattr(gh.subprocess, "run", run)

    assert gh_api("repos/o/r/rules/branches/main", paginate=True) == [
        {"type": "deletion"},
        {"type": "pull_request"},
    ]
    assert run.calls == [["gh", "api", "--paginate", "--slurp", "repos/o/r/rules/branches/main"]]


@pytest.mark.parametrize(
    "fixture,message",
    [
        ("protection_absent.json", "Branch not protected"),
        ("protection_no_admin.json", "Not Found"),
    ],
)
def test_http_error_carries_status_and_message(monkeypatch, fixture, message):
    body = (FIXTURES_DIR / fixture).read_text()
    monkeypatch.setattr(
        gh.subprocess, "run", fake_run(body, returncode=1, stderr=f"gh: {message} (HTTP 404)")
    )

    with pytest.raises(GhApiError) as exc_info:
        gh_api("repos/o/r/branches/main/protection")
    assert exc_info.value.status == 404
    assert exc_info.value.message == message


def test_paginated_http_error_carries_status_and_message(monkeypatch):
    body = load_fixture("rules_plan_unavailable.json")
    monkeypatch.setattr(gh.subprocess, "run", fake_run(json.dumps([body]), returncode=1))

    with pytest.raises(GhApiError) as exc_info:
        gh_api("repos/o/r/rules/branches/main", paginate=True)
    assert exc_info.value.status == 403
    assert exc_info.value.message == body["message"]


def test_non_http_error_uses_stderr(monkeypatch):
    stderr = "unable to expand placeholder in path: no git remotes found\n"
    monkeypatch.setattr(gh.subprocess, "run", fake_run("", returncode=1, stderr=stderr))

    with pytest.raises(GhApiError) as exc_info:
        gh_api("repos/{owner}/{repo}")
    assert exc_info.value.status is None
    assert exc_info.value.message == "unable to expand placeholder in path: no git remotes found"


def test_missing_gh_raises_gh_api_error(monkeypatch):
    def run(args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "gh")

    monkeypatch.setattr(gh.subprocess, "run", run)

    with pytest.raises(GhApiError) as exc_info:
        gh_api("repos/o/r")
    assert exc_info.value.status is None
    assert "gh" in exc_info.value.message
