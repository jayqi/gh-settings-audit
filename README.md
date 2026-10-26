# gh-settings-audit

Check one GitHub repository's settings and default-branch rules against my preferred values, and report where they differ. It only reports; it doesn't change anything.

## Requirements

- [GitHub CLI (`gh`)](https://cli.github.com/) 2.48 or later, authenticated. All API calls go through `gh api`.

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
Repository: drivendataorg/cloudpathlib
Default branch: master

Repo settings
  ok       allow_merge_commit: false
  ok       allow_squash_merge: true
  ok       allow_rebase_merge: true
  differs  squash_merge_commit_title: "COMMIT_OR_PR_TITLE" (preferred "PR_TITLE")
  differs  squash_merge_commit_message: "COMMIT_MESSAGES" (preferred "BLANK")
  ok       allow_update_branch: true
  ok       delete_branch_on_merge: true

Default branch rules
  differs  deletion blocked: deletion rule present, but bypassable (ruleset "Tests Pass": always)
  differs  force pushes blocked: non_fast_forward rule present, but bypassable (ruleset "Tests Pass": always)
  differs  linear history required: no required_linear_history rule
  differs  pull requests required: no pull_request rule
  ok       classic branch protection: not used

Summary: ok: 6, differs: 6, unknown: 0
```

Each check line starts with one of these statuses:

- `ok`: matches the preferred value.
- `differs`: doesn't match the preferred value. This may be deliberate.
- `unknown`: couldn't be read with your access or the repository's plan.

In a terminal, statuses also get a symbol and color (`✓` green, `~` yellow, `?` dim). Piped output is plain text. Set `NO_COLOR` to turn off color in a terminal.

The exit code is 0 whenever a report is produced, even if settings differ. It's nonzero only when no report could be produced, for example when the repository can't be resolved or an API call fails.

## Checks

The preferred values are defined in [`checks.py`](src/gh_settings_audit/checks.py).

**Repo settings** (from `GET /repos/{owner}/{repo}`):

| Field | Preferred |
|---|---|
| `allow_merge_commit` | `false` |
| `allow_squash_merge` | `true` |
| `allow_rebase_merge` | `true` |
| `squash_merge_commit_title` | `"PR_TITLE"` |
| `squash_merge_commit_message` | `"BLANK"` (with the title setting, "Pull request title" only) |
| `allow_update_branch` | `true` |
| `delete_branch_on_merge` | `true` |

Reading these fields requires write access to the repository.

**Default-branch rules** come from rulesets, using the active rules GitHub reports for the default branch (`GET /repos/{owner}/{repo}/rules/branches/{branch}`). This includes rules from both repository and organization rulesets. Each check is `ok` if a rule of that type applies and at least one ruleset providing it has no bypass actors:

| Check | Rule type |
|---|---|
| deletion blocked | `deletion` |
| force pushes blocked | `non_fast_forward` |
| linear history required | `required_linear_history` |
| pull requests required | `pull_request` |

Bypass is set per ruleset, and covers every rule in that ruleset. When every ruleset providing a rule allows bypass, the check shows `differs` and names those rulesets and their bypass modes. Reading a ruleset's bypass list requires admin access; without it, the check is `unknown`. On a private repository whose plan doesn't support rulesets, these checks show `differs`.

**Classic branch protection** isn't checked rule by rule. If the default branch uses it, the check shows `differs`, since rulesets are preferred. You can migrate under Settings → Rulesets.

To see the rules GitHub applies to a repository's default branch yourself:

```bash
gh ruleset check --default -R OWNER/REPO
```

## Development

See [`AGENTS.md`](AGENTS.md) for the `just` commands for testing, linting, and type checking. Tests run against saved API responses in [`tests/fixtures`](tests/fixtures).
