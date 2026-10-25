# gh-settings-audit

Check one GitHub repository's settings and default-branch rules against my preferred values, and report where they differ. It only reports; it doesn't change anything.

## Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/), authenticated. All API calls go through `gh api`.

## Usage

Run without installing:

```bash
uvx --from git+https://github.com/jayqi/gh-settings-audit gh-settings-audit OWNER/REPO
```

Or install it as a tool:

```bash
uv tool install git+https://github.com/jayqi/gh-settings-audit
```

With no argument, it checks the current directory's repository, resolved the same way `gh` does (including the `GH_REPO` environment variable).

Example output:

```text
Repository: jayqi/python-package-reference
Default branch: main

Repo settings
  PASS     allow_merge_commit: false
  FAIL     squash_merge_commit_title: "COMMIT_OR_PR_TITLE" (expected "PR_TITLE")
  FAIL     squash_merge_commit_message: "COMMIT_MESSAGES" (expected "BLANK")
  PASS     allow_update_branch: true
  PASS     delete_branch_on_merge: true

Default branch rules
  FAIL     has protection: no ruleset rules apply
  FAIL     no force pushes: no non_fast_forward rule
  FAIL     linear history: no required_linear_history rule
  FAIL     require pull requests: no pull_request rule
  PASS     classic branch protection: not used

Summary: 4 PASS, 6 FAIL, 0 WARN, 0 UNKNOWN
```

Each check line starts with one of these statuses:

- `PASS`: matches the preferred value.
- `FAIL`: doesn't match.
- `WARN`: works, but should change.
- `UNKNOWN`: couldn't be read with your access or the repository's plan.

The exit code is 0 whenever a report is produced, even if checks fail. It's nonzero only when no report could be produced, for example when the repository can't be resolved or an API call fails.

## Checks

The expected values are defined in [`checks.py`](src/gh_settings_audit/checks.py).

**Repo settings** (from `GET /repos/{owner}/{repo}`):

| Field | Expected |
|---|---|
| `allow_merge_commit` | `false` |
| `squash_merge_commit_title` | `"PR_TITLE"` |
| `squash_merge_commit_message` | `"BLANK"` (with the title setting, "Pull request title" only) |
| `allow_update_branch` | `true` |
| `delete_branch_on_merge` | `true` |

Reading these fields requires admin access to the repository.

**Default-branch rules** come from rulesets, using the active rules GitHub reports for the default branch (`GET /repos/{owner}/{repo}/rules/branches/{branch}`). This includes rules from both repository and organization rulesets. Each check passes if a rule of that type applies:

| Check | Rule type |
|---|---|
| has protection | any rule |
| no force pushes | `non_fast_forward` |
| linear history | `required_linear_history` |
| require pull requests | `pull_request` |

**Classic branch protection** isn't checked rule by rule. If the default branch uses it, the report warns you to migrate to rulesets, which you can do under Settings → Rulesets. Seeing classic protection requires admin access; without it, this check is `UNKNOWN`.

To see the rules GitHub applies to a repository's default branch yourself:

```bash
gh ruleset check --default -R OWNER/REPO
```

## Development

See [`AGENTS.md`](AGENTS.md) for the `just` commands for testing, linting, and type checking. Tests run against saved API responses in [`tests/fixtures`](tests/fixtures).
