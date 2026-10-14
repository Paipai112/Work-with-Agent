# Delivery scope and local checkpoints

Scope and checkpoint sections are independently loaded for their respective operation.

## Scope

Verify [claim/session](claims-and-handoffs.md) before scoped Commit. Examples use this package's read-only `scripts/collaboration_scope.py`, Python 3.11+ standard library, from package root.

```sh
python scripts/collaboration_scope.py --input scope-input.json
python scripts/collaboration_scope.py --repo /absolute/project --base FULL_COMMIT_SHA --scope scope.json --other-claims other-claims.json
```

JSON: nonempty `scope` patterns, `changes`, optional `other_claims`. Changes have `status: added|modified|deleted|renamed|untracked`, `path`, and rename `previous_path`; other claims have `claim_url`/`scope`. Supply current verified allocations: helper cannot establish active claims.

Git mode unions base→HEAD, HEAD→index, index→worktree and nonignored untracked paths separately, preventing cancellation. Both rename ends and low-similarity delete/add moves count. Ignored untracked delivery needs explicit JSON inventory. Fixed local objects only: no replace objects/lazy fetch; unsupported Git/missing objects → unknown. No staging/Commit/network/Push.

Repository-relative POSIX: literals exact, `*`/`?` one segment, whole-segment `**` zero-or-more directories, terminal `**` descendants. `tests/*.py` excludes `tests/unit/a.py`; `tests/**/a.py` includes it and `tests/a.py`. No character classes, embedded `**`, absolute/traversal paths.

Outputs `paths`, `out_of_scope`, path/claim-URL `conflicts`; pass means supplied inventory fits without listed overlap, not authority (`authorization_verified: false`). Resolve changes/conflicts before writes. Exits: 0 pass, 1 scope/conflict, 2 invalid/unavailable.

## Checkpoint

Use for interruption/resume progress only, not claim release or resume/Push authority.

```sh
python scripts/collaboration_scope.py --checkpoint checkpoint-input.json
```

Fields: `repository`, `issue_number`, `actor_id`, `session_id`, `claim_url`, `completed`, `tests`, `uncommitted_changes`, `remaining_steps`; optional code `branch`/full `head_sha`, research `artifact_urls`, bound PID/time/coordinator `process_observation`. Tests record `command`/observed `status: pass|fail|unknown`; changes use Scope inventory. No credentials/raw sensitive output.

Validated stdout record: preserve old records when saving. Permission/claim-state inputs fail; output always `old_process_status: unknown`, `claim_released: false`, `push_authorized: false`, `authorization_verified: false`. No release/resume/Git write/process termination; silence/missing process proves no stop.

Resume refreshes repository/account/actor/session/lineage/branch/HEAD. Same branch requires verified handoff or current direct stop confirmation; unknown process uses independent-branch reassignment. Checkpoint grants no transition authority.
