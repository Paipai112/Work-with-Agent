# Issues and accepted results

Read [preflight](preflight.md) first. Issue creation and ordinary discussion need verified identity and the user's requested scope, but no existing implementation claim.

## Create or select an Issue

1. Read the project's README context index and follow its authoritative requirement, specification, decision, progress and validation sources. Mark missing sources unknown; keep each fact authoritative in one place.
2. Search open and relevant closed Issues/PRs for the same request. Reuse an Issue when its scope and acceptance match; clarify a material conflict. Otherwise create an Issue with purpose, boundaries, acceptance criteria, dependencies, durable source links, and expected delivery (`code` or `research`). Use the project's Issue template and existing labels where applicable. Do not invent owners, dates or decisions.
3. Read back the created Issue number, URL, body and state before [claiming its scope](claims-and-handoffs.md). An uncertain creation response requires duplicate lookup before retry. Finish this step with one verified Issue and a clear next operation.

## Research or decision delivery

Use `task_kind: research` for work delivered as an Issue comment or another durable linked artifact without repository file edits. The [research claim](../templates/events/research-claim.yml) names the question/decision scope and expected accepted result; omit branch and SHA fields. Publish the result with sources, findings, decisions versus proposals, unknowns, acceptance evidence and remaining work. A transient chat summary alone is not delivery.

Have the acceptance authority specified in the Issue/project or the requesting user accept the result; record the accepted artifact version/URL and evidence in the Issue, verifying any GitHub comment's real author. If acceptance authority is unknown or the criteria are unmet, keep the Issue open and state the missing condition. After verified acceptance and applicable closure authority, post a self-release linked to the claim, preserve the artifact and acceptance links, close only completed scope, and read back the Issue and event. Branchless handoff/resume/release carry `artifact_urls` pointing to the current durable result or progress record; they never claim a nonexistent commit.

If delivery edits repository files, switch to a code claim with a verified base/branch and the [Git/PR procedure](git-and-pull-requests.md). Partial results and internal integration merges leave unfinished Issues open. A PR can close several accepted Issues, but every explicit closing reference must agree with `closes_issues` metadata.
