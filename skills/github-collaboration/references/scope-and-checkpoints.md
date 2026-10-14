# Delivery scope and local checkpoints

Use before a scoped commit or when preserving interruption/resume progress. Verify current claim/session facts via [claims and handoffs](claims-and-handoffs.md). The package's `scripts/collaboration_scope.py` is read-only and requires Python 3.11+ standard library only. Examples assume package root.

## Scope

```sh
python scripts/collaboration_scope.py --input scope-input.json
python scripts/collaboration_scope.py --repo /absolute/project --base FULL_COMMIT_SHA --scope scope.json --other-claims other-claims.json
```

JSON input has `scope` (nonempty pattern list), `changes`, optional `other_claims`. Each change has `status: added|modified|deleted|renamed|untracked`, `path`; renames also have `previous_path`. Competing claims have `claim_url` and `scope`. Supply verified current allocations; this helper does not determine whether a claim is active.

Git mode separately combines base-to-HEAD commits, HEAD-to-index changes, index-to-worktree changes and nonignored untracked files. Opposing staged/unstaged changes cannot hide a path through net cancellation. It checks both rename paths and performs no staging, commit, network or push. Ignored untracked delivery files require explicit JSON inventory. Low-similarity moves may appear as deletion/addition; both paths are checked.

Use repository-relative POSIX paths. Literals match exactly; `*`/`?` stay within one segment, whole-segment `**` spans zero or more directory segments, terminal `**` spans descendants. `tests/*.py` excludes `tests/unit/a.py`; `tests/**/a.py` includes that path and `tests/a.py`. Character classes, embedded `**`, absolute paths and traversal are rejected.

Results list `paths`, `out_of_scope` and path/claim-URL `conflicts`. Pass means only supplied inventory/patterns fit with no listed overlap. `authorization_verified` remains false. Resolve scope changes/conflicts before affected writes. Exit codes: 0 comparison pass, 1 out-of-scope/conflict, 2 invalid/unavailable input.

## Checkpoint

```sh
python scripts/collaboration_scope.py --checkpoint checkpoint-input.json
```

Record `repository`, `issue_number`, `actor_id`, `session_id`, `claim_url`, `completed`, `tests`, `uncommitted_changes`, `remaining_steps`. Code may add `branch`/full `head_sha`; research may add `artifact_urls`. Tests name `command` and observed `status: pass|fail|unknown`; changes follow the scope inventory fields. Optional `process_observation` preserves a bound PID/time/coordinator observation. Exclude credentials/raw sensitive output.

The validated record goes to stdout; preserve existing records when saving it. Permission/claim-state input fields are rejected. Output always says `old_process_status: unknown`, `claim_released: false`, `push_authorized: false`, `authorization_verified: false`. Missing process or silence never establishes termination. The helper performs no release, resume, Git write or process termination.

Refresh repository, actor/account, claim lineage, branch/HEAD and session facts on resume. Same-branch resume requires verified handoff or current direct stop confirmation; an unknown old process uses independent-branch reassignment. A checkpoint reconstructs progress and cannot authorize that transition.
