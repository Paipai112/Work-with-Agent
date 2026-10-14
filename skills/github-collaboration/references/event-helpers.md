# Event candidates, publication and correction

Use for constructing, validating, publishing or correcting an event after [preflight](preflight.md) and the applicable [claims and handoffs](claims-and-handoffs.md) gates. Helper success does not verify human consent, effective role, active ownership, competing allocation or process termination.

## Candidate

Run the verified package's `scripts/collaboration_event.py`; examples assume that package root. Python 3.11+, PyYAML and jsonschema are required. Use the reviewed `requirements-helpers.txt` or source project's `[helpers]` extra in your selected environment. Missing dependencies return `unknown`; the helper never installs them. Scope/checkpoint operations remain standard-library-only.

```sh
python scripts/collaboration_event.py construct --template claim --fields fields.json
python scripts/collaboration_event.py validate --body candidate.md
```

`fields.json` explicitly overrides the actual bundled template; inspect all remaining example values. Names are `claim`, `research-claim`, `handoff`, `reassign`, `release`, `resume`. Research-claim emits `event: claim` with `task_kind: research`. Validation uses the bundled Draft 2020-12 schema and format checks, never another installed Skill's schema.

Bodies are pure YAML or one `yaml`/`yml` fence with optional outside explanation. Multiple candidate fences, unclosed fences or an unfenced event beside a fence are rejected. Duplicate keys, anchors, aliases, merges, explicit tags, directives, multiple documents and ambiguous scalars are rejected. Quote strings resembling numbers/booleans. Diagnostics show location without body excerpts.

## Preview, then explicit write

```sh
python scripts/collaboration_event.py apply --plan event-plan.json
```

Preview uses local inputs only. A plan supplies `operation: publish|append-correction|edit`, `repository` (`hostname`, immutable numeric `id`, `owner`, `name`), `issue_number`, `expected_author` (`user_id`, `login`) and exact `body`. Correction/edit also supply original `comment_id`, canonical `comment_url` and `old_body_sha256` of its UTF-8 body. Actor/session identity remains in the event.

Preview returns `required_approval` bound to operation, repository ID, Issue, comment ID and old/new digests. Obtain external authorization and explicit confirmation for this exact proposal, then record that object in the plan's `approval`. A file's boolean records the input; it cannot prove human consent. Target/body changes require fresh exact confirmation.

```sh
python scripts/collaboration_event.py apply --plan event-plan.json --write --receipt event-receipt.json
```

Writes require authenticated `gh`. The helper GETs repository, current account, open Issue and referenced comments, sends one scoped request, then GETs the result. It verifies exact ID/URL, repository/Issue, author ID/login and body. Output matches collector fields: `id`, `url`, `user_id`, `login`, `issue_number`, `body`, `updated_at`. Refresh remaining allocation/permission facts before relying on the event. CLI status/exit pairs are `pass`/0, `fail`/1, `unknown`/2; `authorization_verified` stays false.

## Correction and unknown result

Prefer `append-correction`, retaining the original. Give the new event a new `event_id` and `revision`: `kind: correction`, `original_event_id`, original `github_comment_id`/`github_comment_url`, `old_body_sha256`, `reason`. These links/digests are verified. This does not retroactively approve scope or baseline changes. Authorized `edit` preserves event kind/ID, account, actor and session; it compares the old body immediately before PATCH and GETs afterward. Concurrent later changes still require reconciliation.

The receipt is created exclusively before sending and stores target IDs/digests/state without raw body or credentials. Regular files and directory paths are required; symlinks or different recorded targets/digests stop without overwrite. `read-back-verified` confirms the result. `write-sent-result-unknown` permits only read-back; reusing that receipt cannot repeat an unresolved POST/PATCH. Preserve it; replacement/deletion is not a recovery procedure. Another process using another receipt can still race, so resolve shared event IDs/allocations through the protocol. A timeout is not failure evidence; follow [failure recovery](failure-recovery.md).
