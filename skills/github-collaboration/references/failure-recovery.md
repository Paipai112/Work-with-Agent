# Failure recovery

Preserve worktree/index/untracked files, commits and remote evidence. Record attempted operation/target, expected SHA, known request/comment IDs, observed result and unknowns without credentials. No force push, destructive reset, discarded work or review/protection bypass.

1. Read-only inspect Git/local-remote refs, PR/Issue/events and default HEAD. Distinguish confirmed success, confirmed failure and unknown; unknown stops retry until GET resolves it.
2. Divergence compares expected/actual HEAD, ancestry and claim/handoff/reassign state; retain both histories for scoped reconciliation. Uncertain Push/merge verifies remote ref, merged state/SHA and approved-target reachability. Integration is not default delivery.
3. Changed HEAD/permission/checks/reviews/conversations or governance routing stops that gate. Refresh current-HEAD evidence and route governance through setup; old approval/green results are insufficient.
4. Verified merge plus failed Issue/event follow-up: inspect existing records, add only the missing idempotent update bound to verified PR/merge SHA, then GET. Keep merge proof; no duplicate closure/handoff or rewritten merge.

Report facts, preserved work, exact blocker, safe options and required decision. Resume only with current state/authority. Event receipt and checkpoint details are in [event helpers](event-helpers.md) and [scope/checkpoints](scope-and-checkpoints.md); a receipt is not permission to repeat an unresolved request.
