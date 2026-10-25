import argparse
import re
import sys

from gh_settings_audit.checks import audit
from gh_settings_audit.gh import Api, GhApiError, gh_api
from gh_settings_audit.report import format_report

PROG = "gh-settings-audit"


def repo_name(value: str) -> str:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
        raise argparse.ArgumentTypeError(f"expected OWNER/REPO, got {value!r}")
    return value


def main(argv: list[str] | None = None, api: Api = gh_api) -> int:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Check a GitHub repository's settings and default-branch rules against preferred "
            "values. Exits 0 whenever a report is produced, even if checks fail."
        ),
    )
    parser.add_argument(
        "repo",
        nargs="?",
        type=repo_name,
        metavar="OWNER/REPO",
        help="repository to check (default: the current directory's repository, like gh)",
    )
    args = parser.parse_args(argv)

    try:
        report = audit(args.repo, api=api)
    except GhApiError as e:
        print(f"{PROG}: error: {e}", file=sys.stderr)
        return 1
    print(format_report(report), end="")
    return 0
