# Claims, handoffs and reassignment

Use [preflight](preflight.md); Leader actions add [identity/permissions](identity-and-permissions.md). Comments/timestamps/posting are not locks; silence/missing processes prove no termination.

## Event evidence and helpers

Validate raw bodies with this package's `references/schemas/collaboration-event.schema.json`, Draft 2020-12/`FormatChecker()`; missing/incompatible schema stops writes. GET real comment host/repository ID/owner/name/Issue/ID/URL/author ID/login; match `controlled_by_id`/`controlled_by`. GET predecessors, match same-repository/Issue event IDs/links; resolve edits/duplicates/contradictions. `github_comment_id/url` is the published predecessor, not draft; capture new event's own ID/URL. Schema verifies no consent/role/allocation/process state.

Construction/publication/correction/uncertain results load [event helpers](event-helpers.md). Delivery scope loads **Scope** in [scope/checkpoints](scope-and-checkpoints.md); interruption/resume adds **Checkpoint**. Helpers grant no authority or dependency installation.

## Claim

1. Verify assigned/authorized-queue open Issue, account/actor/session and related Issues/PRs/events/scopes, including same-actor sessions. Resolve overlaps. First claim needs no prior claim; missing Issue uses [Issues/results](issues-and-results.md).
2. Fill [claim](../templates/events/claim.yml) or [research claim](../templates/events/research-claim.yml), unique event ID. Code: proposed Issue branch/verified base, branch created after read-back. Research: decision/result scope, no invented branch/SHA. `previous_event_id: null` only for first claim; successors link terminal handoff/self-release/reassign and real comment ID/URL.
3. Validate/publish/capture ID/URL, then GET envelope/allocations again. Ownership requires matching identity/session/branch/scope, no conflict; newest comment wins nothing. Unknown response needs GET before retry.

Local subagents need explicit parent scope; independent writers need own identity/claim. Before Push recheck lineage/conflicts/remote HEAD; drift stops writes, no force/bypass.

## Handoff, self-release and resume

Owner publishes [handoff](../templates/events/handoff.yml) or [release](../templates/events/release.yml): predecessor, remaining work, successor. `release_mode: self` requires old account/actor, never Leader impersonation. Code carries verified branch/HEAD; research durable `artifact_urls`, no Git fields. Allocation cannot revoke credentials/stop processes.

Same-account/actor [resume](../templates/events/resume.yml) requires verified owner handoff relinquishing writes, or current user's direct confirmation the named old process stopped. Record direct confirmation, publish/GET self-release under original account/actor **before** resume; shared-account comments cannot prove consent. Link terminal handoff/self-release ID/URL, verify same branch/current HEAD, GET competing allocations after posting. Different actor needs new claim; unknown process uses independent-branch reassignment.

## Leader reassignment

Refresh executing Leader's default-branch grant/account, human allocation decision and lineage. Publish [reassign](../templates/events/reassign.yml) as **that Leader**, never proxy release:

- `target`: prior claim event/comment/account/actor/session, old scope/branch/base, latest predecessor.
- `successor`: exact new account/actor/session; verified `approval_url` and reason.
- `old_process_status`: unknown/null stop evidence, or stopped/independently verified evidence. Leader assertion/timeout/shared-account comment proves no termination.

GET event/author/authority/approval/lineage. Valid reassign supersedes exact old allocation; successor publishes/GETs new linked claim. Unknown process: retain old branch/worktree, distinct Issue branch from verified permitted base, inspect old commits before separate integration; no remote termination claim. Returning sessions refresh/stop superseded writes. Unknown/conflicting authority leaves scope read-only, never revives old claims. Research needs new claim/durable result lineage.
