import json
import subprocess
from typing import Any, Protocol


class GhApiError(Exception):
    """A `gh api` call failed. `status` is the HTTP status, or None if no response was received."""

    def __init__(self, status: int | None, message: str):
        self.status = status
        self.message = message
        super().__init__(f"{message} (HTTP {status})" if status is not None else message)


class Api(Protocol):
    def __call__(self, endpoint: str, paginate: bool = False) -> Any: ...


def gh_api(endpoint: str, paginate: bool = False) -> Any:
    """Make a GET request with `gh api` and return the parsed JSON response.

    `{owner}` and `{repo}` placeholders in the endpoint resolve to the current directory's repo.
    With `paginate`, the endpoint must return a JSON array; pages are concatenated.
    """
    args = ["gh", "api", *(["--paginate", "--slurp"] if paginate else []), endpoint]
    try:
        proc = subprocess.run(args, capture_output=True, encoding="utf-8")
    except FileNotFoundError:
        raise GhApiError(
            None, "gh not found; install GitHub CLI from https://cli.github.com/"
        ) from None
    if proc.returncode != 0:
        # On HTTP errors, gh prints the response body (with "message" and "status") to stdout,
        # wrapped in an array with --slurp
        try:
            body = json.loads(proc.stdout)
            if paginate:
                (body,) = body
            status, message = int(body["status"]), body["message"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise GhApiError(None, proc.stderr.strip()) from None
        raise GhApiError(status, message)
    data = json.loads(proc.stdout)
    if paginate:
        return [item for page in data for item in page]
    return data
