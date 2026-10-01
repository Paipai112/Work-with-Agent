# Resume and recovery of setup operations

Use this reference when setup stops after a local edit, Commit, Push, PR, remote API call, lost network reply, or session handoff. A resume record helps reconstruct progress; it is never a Leader grant or proof that a user approved today's changed diff. Re-run [preflight](preflight-and-identity.md), [authorization](authorization.md), [local configuration](local-configuration.md), and [managed resource](managed-resources.md) checks for the action actually being resumed.

## Minimal operation record

Keep a stable `operation_id` across retries and session handoff. The record must contain the verified repository hostname/immutable ID/owner/name/default branch and source SHA, current branch and base/HEAD SHA, actor ID/controlling account ID/session ID, selected mode, canonical template version, and each resource's kind, stable path or remote ID, baseline reference, plan-time current digest, proposed digest, approval evidence and scope, application state, read-back digest and remote result ID. Also record completed Commit SHA, pushed branch/remote HEAD, PR number/URL where applicable, each Actions/setting/check/ruleset approval separately, unresolved errors, and one `next_safe_action`. Keep the record free of tokens and do not assume its local copy is current or tamper resistant.

Use states such as `planned`, `approved`, `write-sent-result-unknown`, `read-back-verified`, and `blocked`; a successful API response without read-back is not `read-back-verified`. Store exact old and new identifiers and timestamps as observations. If there is no reliable record, rebuild a new read-only inventory and plan rather than guessing which steps ran.

## Resume decision

1. Verify the repository, authenticated account, effective Agent role, current default-branch authorization, source SHA, session grant, protections, and branch HEAD again. A scoped Bootstrap/Recovery grant from the old session does not transfer; get a fresh explicit human grant bound to the current identity and proposal if needed.
2. Compare each current resource with its recorded baseline and approved digest. A changed digest, different target ID, changed source SHA, revoked role, or expired/unclear approval invalidates that item. Show a new diff and seek a new approval before touching it. Completed, read-back-verified items are not replayed.
3. If a local write or Commit may already have happened, inspect target bytes, Git status, index, commit SHA and parent. Do not reset, delete user edits, or stage broad paths. Report what exists and choose the next separately approved Git action.
4. If Push or PR creation may have happened, query the exact remote branch HEAD and PR by repository, source branch, head/base and operation context. If ambiguous, stop. Never force push to reconcile automatically.
5. If a remote mutation reply was lost, query by stable remote ID and compare approved managed fields. For a create without a returned ID, search its exact repository/type/name or path, require a unique match, then store the discovered ID. Only retry after confirming no matching mutation occurred and rechecking authorization plus approval of the still-current diff.
6. Read back and record one item at a time. Give the user a completion/partial-result report listing verified, unchanged, blocked, and uncertain resources with IDs, digests, and next safe actions.

Neither GitHub APIs nor a pure Skill offer a transaction across files, Git, and remote settings. A pre-write comparison cannot prevent every concurrent edit. Treat conflicts and uncertain outcomes as states to inspect, not as reasons to delete or replace work. Preserve user data and current protection while a human decides the unresolved item.
