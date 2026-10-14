# Event candidates, publication and correction

Use after [preflight](preflight.md) and applicable [claim gates](claims-and-handoffs.md). Helpers verify no consent, role, current ownership/competition or process termination.

## Candidate

Examples run from the verified package root: Python 3.11+, PyYAML/jsonschema from reviewed `requirements-helpers.txt` or source `[helpers]` extra. Missing dependencies return unknown, never auto-install; scope/checkpoints use only standard library.

```sh
python scripts/collaboration_event.py construct --template claim --fields fields.json
python scripts/collaboration_event.py validate --body candidate.md
```

`fields.json` overrides the bundled template; inspect remaining example values. Templates: `claim`, `research-claim`, `handoff`, `reassign`, `release`, `resume`; research emits `event: claim`, `task_kind: research`. Validation uses this package's Draft 2020-12 schema/formats, never another Skill's.

Use pure YAML or one closed `yaml`/`yml` fence with optional outside explanation, no extra event/fence. Duplicate keys, anchors/aliases/merges/tags/directives/multiple documents/ambiguous scalars fail; quote number/boolean-like strings. Diagnostics report location, no body excerpts.

## Preview, then explicit write

```sh
python scripts/collaboration_event.py apply --plan event-plan.json
```

Local-only preview requires `operation: publish|append-correction|edit`, `repository` (`hostname`, immutable numeric `id`, `owner`, `name`), `issue_number`, `expected_author` (`user_id`, `login`), exact `body`; correction/edit adds original `comment_id`, canonical `comment_url`, UTF-8 `old_body_sha256`. Event carries actor/session.

Obtain external authorization/explicit confirmation of `required_approval` (operation/repository ID/Issue/comment ID/old-new digests), then record it as `approval`. Its boolean cannot prove consent; changed target/body requires fresh confirmation.

```sh
python scripts/collaboration_event.py apply --plan event-plan.json --write --receipt event-receipt.json
```

Authenticated `gh` GETs repository/account/Issue/referenced comments, sends one scoped request, then GET-verifies ID/URL/repository/Issue/author/body. Self-release may target a closed Issue after completion; all other events require an open Issue, with every repository/account/predecessor binding retained. Output collector fields: `id`, `url`, `user_id`, `login`, `issue_number`, `body`, `updated_at`. Refresh allocation/permissions separately. Status/exits: `pass`/0, `fail`/1, `unknown`/2; `authorization_verified: false`.

## Correction and unknown result

Prefer `append-correction`: retain original, new `event_id`, `revision` with local `schema_version: 1`, `kind: correction`, `original_event_id`, original `github_comment_id`/`github_comment_url`, `old_body_sha256`, `reason`. Links/digests are verified; no retroactive scope/baseline approval. Missing/unsupported revision version fails; matched reviewed helper/schema required, no silent migration. Unrevised legacy events retain root v1. Authorized `edit` preserves kind/ID/account/actor/session, compares old body before PATCH and GETs afterward; later concurrent edits need reconciliation.

Baseline change: original event kind/new event ID, revision `kind: baseline`. Its ID/URL/old-body SHA256 fields bind the **original root claim**, with reason; `from_base_head` = previous effective baseline, `to_base_head` = new `base_head`. Retain original comment. Scope must stay unchanged, as must account/actor/branch/session; expansion needs separate new claim/preflight, not retrospective authorization. Follow [fixed delivery](git-and-pull-requests.md).

Receipt is exclusively created before sending: IDs/digests/state, no raw body/credentials. Symlinks/nonregular paths or mismatched recorded target/digest stop without overwrite. `read-back-verified` confirms result; `write-sent-result-unknown` allows GET only, never repeating unresolved POST/PATCH. Preserve receipt; replacing/deleting it is not recovery. Another receipt/process can race: reconcile event IDs/allocations via protocol. Timeout is not failure; use [recovery](failure-recovery.md).
