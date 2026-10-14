# Issues and accepted results

Use [preflight](preflight.md). Issue creation/discussion needs identity and requested scope, not an existing implementation claim.

1. Follow the project README's authoritative requirement/design/decision/progress/validation pointers; missing/conflicting facts stay unknown.
2. Search open and relevant closed Issues/PRs. Reuse matching scope/acceptance or resolve conflicts; otherwise use the project's template/labels with outcome, boundaries, acceptance, dependencies, durable sources and `code`/`research` delivery. Invent no owner/date/decision.
3. Create only within the assignment, GET the actual Issue number/URL/body/state, then [claim](claims-and-handoffs.md). An unknown response needs duplicate lookup before retry.

## Accepted research

A `task_kind: research` [claim](../templates/events/research-claim.yml) records question/decision scope and expected durable result, with no invented branch/SHA. Publish sources, findings, accepted decisions versus proposals, unknowns, acceptance evidence and remaining work; transient chat alone is not delivery.

The Issue/project acceptance authority or requesting user must accept the identified artifact/version. Verify any acceptance comment's real author. Unknown authority or unmet criteria keeps the Issue open. After accepted scope and closure authority are verified, publish self-release linked to the claim, close only completed scope and GET event/Issue state. Branchless transfer events carry current `artifact_urls`.

Repository-file delivery uses a code claim and [Git/PR](git-and-pull-requests.md). Partial delivery/internal integration leaves unfinished Issues open; every explicit closing statement must match PR `closes_issues`.
