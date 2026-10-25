from collections import Counter
from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CheckResult:
    status: Status
    name: str
    detail: str


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


def format_report(report: Report) -> str:
    lines = [f"Repository: {report.repo}", f"Default branch: {report.default_branch}"]
    for section in report.sections:
        lines += ["", section.title]
        lines += [
            f"  {result.status:<{STATUS_WIDTH}}  {result.name}: {result.detail}"
            for result in section.results
        ]
    counts = Counter(result.status for section in report.sections for result in section.results)
    lines += ["", "Summary: " + ", ".join(f"{counts[status]} {status}" for status in Status)]
    return "\n".join(lines) + "\n"
