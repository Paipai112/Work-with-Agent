# Select a check

Use the helper path inside this verified package. Do not execute scripts from a PR,
substitute a saved SHA for a live default-branch query, or send credentials in chat.
Use the user's authenticated `gh` client; missing access remains unknown.

## Formal PR metadata

Run the package's `scripts/run_pr_metadata_check.py` with Python 3.11 or later:

```text
python3 <verified-package>/scripts/run_pr_metadata_check.py --repository OWNER/REPO --pull-number N --repository-id ID --expected-head FULL_SHA --output-dir NEW_LOCAL_REPORT_DIRECTORY
```

Replace placeholders with confirmed target facts. The report directory is a local
check artifact, not a repository edit; inspect an existing destination before use.
The launcher independently queries the default branch and fetches the deployed
trusted resources at that SHA. `--expected-trusted-sha` is an optional drift guard,
not an override of that query. It never falls back to candidate templates if the
deployed chain is missing, incompatible or unreadable.

Exit `0` with `result: pass` means the checks covered by the report passed. Exit `1`
is a known failure; exit `2` is unknown/unavailable and must not be presented as
passing. Read the actual JSON result and errors, not only the process exit status.
The output directory contains the collected `metadata.json` and formal
`check-report.json`. Do not publish raw snapshots without inspecting them for private
Issue/comment content. A collection failure may leave no complete snapshot.

`--collect-only` collects facts without a formal verdict; its successful exit is
**not** PASS. `--default-target-only` restricts applicability to final default-branch
PRs; do not use an inapplicable result to approve an integration PR.

If the trusted checker needs dependencies that are absent, report their verified
requirements and request explicit environment preparation. Do not install them as
part of this check. An Action is optional and is not enabled by running locally.

## Configuration or an event without a PR

Separate syntax/schema diagnostics from a live authorization decision. For project
configuration, resolve paths using the verified default-branch config, and read
authorization/protocol at the same SHA. A local candidate can be checked for format
but cannot grant its author permissions. If no formal PR exists, say that PR-level
collection and gates were not run.

For event or scope diagnostics, inspect the relevant comment identity, full event
history and actual changed paths, including both sides of renames. A comment that
exists may already be released, superseded or contested. A missing page, uncertain
old session, unresolved overlap or unverified revision remains a reported gap.
Never use an event publication/edit mode or Git staging command from this Skill.

## Report

Give the verdict and the specific failed or missing check first. Include the exact
target and observed SHAs, actual command/result, collection freshness, unchecked
areas, and the next safe action. Link to the relevant evidence without exposing
tokens or private content. Passing does not replace independent current-HEAD review,
user approvals, repository protections or the required refresh before a later write.
