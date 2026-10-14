# Select a check

Use this verified package's helper and the authenticated `gh` client. Missing access
is unknown. Never execute PR scripts, substitute saved SHA for live default discovery,
or send credentials in chat.

## Formal PR metadata

Run the package's `scripts/run_pr_metadata_check.py` with Python 3.11 or later:

```text
python3 <verified-package>/scripts/run_pr_metadata_check.py --repository OWNER/REPO --pull-number N --repository-id ID --expected-head FULL_SHA --output-dir NEW_LOCAL_REPORT_DIRECTORY
```

Replace placeholders with confirmed facts. Inspect the report destination; use a new
or empty regular directory for local artifacts. The launcher independently discovers
the default SHA and fetches its trusted deployment. `--expected-trusted-sha` guards
drift, never overrides discovery. Missing/incompatible/unreadable deployment has no
candidate-template fallback.

Read JSON result/errors, not exit status alone: `0` + `result: pass` means the stated
checks passed; `1` is failure, `2` unknown/unavailable. Output contains `metadata.json`
and `check-report.json`; failed collection may leave no complete snapshot. Inspect
private Issue/comment content before sharing artifacts.

`--collect-only` success is **not** formal PASS. `--default-target-only` restricts
applicability to default-branch PRs; an inapplicable result cannot approve integration PRs.

Missing dependencies: report verified requirements and request environment preparation,
do not install. Local execution does not enable optional Actions.

## Configuration or an event without a PR

Syntax/schema is not authorization. Resolve project paths from verified default config;
read authorization/protocol at that SHA. Candidate format checks grant no permissions.
Without a PR, report PR-level collection/gates not run.

For events/scope, inspect actual comment identity, complete history and changed paths,
including both rename ends. Existence is not an active claim. Missing pages, uncertain
old sessions, overlaps and unverified revisions remain gaps. Never publish/edit events
or stage Git changes from this Skill.

## Report

Use the entry's report fields; add errors, freshness, unchecked areas and next action.
Link safe evidence, never credentials/private content. PASS replaces no current-HEAD
independent review, approval, protection or refresh before writing.
