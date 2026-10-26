from gh_settings_audit.report import CheckResult, Report, Section, Status, format_report

REPORT = Report(
    repo="o/r",
    default_branch="main",
    sections=[
        Section(
            "Repo settings",
            [CheckResult(Status.UNKNOWN, "allow_merge_commit", "not visible with your access")],
        )
    ],
)


def test_unknown_plain():
    assert format_report(REPORT).splitlines()[4] == (
        "  unknown  allow_merge_commit: not visible with your access"
    )


def test_unknown_colored():
    assert format_report(REPORT, color=True).splitlines()[4] == (
        "  \x1b[2m? unknown\x1b[0m  allow_merge_commit: not visible with your access"
    )
