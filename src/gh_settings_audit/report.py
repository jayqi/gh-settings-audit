from collections import Counter
from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "ok"
    DIFFERS = "differs"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckResult:
    status: Status
    name: str
    detail: str
    # Shown with an arrow under the preceding check
    child: bool = False


@dataclass(frozen=True)
class Section:
    title: str
    results: list[CheckResult]


@dataclass(frozen=True)
class Report:
    repo: str
    default_branch: str
    sections: list[Section]


STATUS_WIDTH = max(len(status) for status in Status)

# Symbol and ANSI color code for each status in terminal output
STATUS_STYLES = {
    Status.OK: ("✓", "32"),
    Status.DIFFERS: ("~", "33"),
    Status.UNKNOWN: ("?", "2"),
}


def format_status(status: Status, color: bool) -> str:
    padding = " " * (STATUS_WIDTH - len(status))
    if not color:
        return f"{status}{padding}"
    symbol, code = STATUS_STYLES[status]
    return f"\x1b[{code}m{symbol} {status}\x1b[0m{padding}"


def format_report(report: Report, color: bool = False) -> str:
    lines = [f"Repository: {report.repo}", f"Default branch: {report.default_branch}"]
    for section in report.sections:
        lines += ["", section.title]
        lines += [
            f"  {format_status(result.status, color)}  {'  ↳ ' if result.child else ''}"
            f"{result.name}: {result.detail}"
            for result in section.results
        ]
    counts = Counter(result.status for section in report.sections for result in section.results)
    lines += ["", "Summary: " + ", ".join(f"{status}: {counts[status]}" for status in Status)]
    return "\n".join(lines) + "\n"
