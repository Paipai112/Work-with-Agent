# Claims, handoffs and reassignment

Use [preflight](preflight.md). Verify Leader-specific actions with [identity/permissions](identity-and-permissions.md). Comments are audit evidence, not locks; timestamps, successful posting, silence or missing local processes prove neither ownership nor termination.

## Event evidence and helpers

Validate raw event bodies with this package's `references/schemas/collaboration-event.schema.json`, Draft 2020-12 and `FormatChecker()`; missing/incompatible schema stops dependent writes. Fetch real comment host/repository ID/owner/name, Issue, ID/URL and author ID/login; match `controlled_by_id`/`controlled_by`. GET predecessors and match event IDs/links in the same repository/Issue. Resolve edited/duplicate/contradictory events. Transfer fields `github_comment_id/url` identify the published predecessor, not the draft; capture a new event's own ID/URL after publishing. Schema checks alone verify no consent, role, allocation or process state.

For candidate construction/schema checks, exact publication/correction or uncertain API results load [event helpers](event-helpers.md). Delivery scope comparison loads **Scope** in [scope/checkpoints](scope-and-checkpoints.md); interruption/resume additionally loads **Checkpoint**. No helper installs dependencies or grants authorization.

## Claim

1. Verify an operator-assigned/authorized-queue open Issue, actor/account/session and current related Issues/PRs/events/scopes, including same-actor sessions. Resolve overlap before writing; first claim needs no prior own claim. Missing Issue uses [Issues/results](issues-and-results.md).
2. Fill actual [claim](../templates/events/claim.yml) or [research claim](../templates/events/research-claim.yml) with unique event ID. Code names proposed Issue branch and verified base; create the branch after claim read-back. Research records decision/result scope without invented branch/SHA. `previous_event_id: null` is first claim only; successors link terminal handoff/self-release/reassign and real comment ID/URL.
3. Validate, publish, capture ID/URL, then GET author/envelope and related allocations again. Ownership needs matching identity/session/branch/scope and no unresolved conflict; newest comment is not a winner. Unknown response requires read-back before retry.

Pure local subagents use explicitly delegated parent scope; independent GitHub writers verify their own identity/claim. Recheck current lineage/conflicts and target remote HEAD before Push; changed allocation/HEAD stops affected writes, with no force or bypass.

## Handoff, self-release and resume

The current owner publishes [handoff](../templates/events/handoff.yml) or [release](../templates/events/release.yml), linking predecessor, remaining work and intended successor. `release_mode: self` requires the old account/actor; Leader cannot impersonate that release. Code carries verified branch/HEAD; research carries durable `artifact_urls` and no Git fields. Allocation changes do not revoke credentials or stop a process.

For same-account/actor [resume](../templates/events/resume.yml), require verified owner handoff relinquishing further writes, or the current user's direct confirmation that the named old process stopped. For direct stop confirmation, record it and publish/read back self-release under original account/actor before resume. Shared-account comments cannot prove human stop confirmation. Link predecessor/handoff fields to terminal handoff/self-release ID/URL, verify same branch/current HEAD and GET competing allocations after posting. A different actor makes a new claim. Unknown process safety uses independent-branch reassignment.

## Leader reassignment

Refresh the executing Leader's current default-branch grant/account, human allocation decision and targeted lineage. Publish [reassign](../templates/events/reassign.yml) as **that Leader**, never proxy release:

- `target`: prior claim event/comment, account/actor/session; old scope/branch/base and latest lineage predecessor.
- `successor`: exact new account/actor/session; verified `approval_url` and reason.
- `old_process_status`: unknown with null stop evidence, or stopped with independently verified evidence. A Leader assertion, timeout or shared-account comment is not termination proof.

GET event/author/current authority, approval and lineage. Valid reassignment supersedes exact old allocation; successor must publish/read back a new linked claim. With unknown old process retain old branch/worktree, use a distinct Issue branch from verified permitted base, inspect any old commits before separate integration, and never claim remote termination. Returning old sessions refresh and stop superseded writes. Unknown/conflicting current authority keeps affected scope read-only; it does not revive old claims. Research also needs new claim and durable result lineage.
