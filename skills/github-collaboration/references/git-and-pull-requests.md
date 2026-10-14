# Issue-linked Git and Draft PR work

Use [preflight](preflight.md) and [current claim verification](claims-and-handoffs.md). Implementation/Git writes require an open Issue and a read-back-verified uncontested claim covering account/actor/session, branch and exact changed scope. Review does not take the implementer's claim.

## Branch and local changes

- Branch `agent/<actor_id>/issue-<primary_issue>-<description>` from verified default SHA, trusted `branch_policy.integration_branches` SHA (absent = empty), or declared predecessor's fixed HEAD through delivery gates below. Integration uses the same naming. Record actual base/ref/SHA; local `main` is unverified, authority remains default-branch based.
- Inspect status, unstaged/staged diff, untracked paths and old/new rename paths against claim scope. Preserve user work; inseparable/conflicting edits need an explicit choice. Validate intended changes and inspect filenames/content for credentials and unrelated generated output without printing secrets.
- Stage inspected exact paths with `git add -- <paths>`; no `git add .`, globs or unscoped `git add -A`. Scoped `git add -A -- <paths>` requires explicit project permission; this project's template forbids every form. Review full cached diff, name/status and `--check` before Commit. Record Issue/actor and real tests; never rewrite another Agent's history or commit daily work on the default branch.

## Governance separation

Compare full changed-file scope and actual diff with trusted managed paths before stage/Commit/Push/Ready. Protocol/config/authorization/registry/schema/checker/templates/workflows/settings and instruction-loading resources are governance. **Complete** registered `managed_paths.entry_files` are governance, including ordinary prose or links outside their block; absent registration defaults to AGENTS.md/CLAUDE.md/CONTRIBUTING.md. Nested AGENTS.md/CLAUDE.md and AGENTS.override.md also qualify. Inspect both rename paths. Missing patch never grants an exemption; obtain the actual diff for approval. Inspect other paths for entry/install-link reachability effects; the checker is a conservative path classifier, not a proof about arbitrary prose.

Keep business work Draft and route a separate governance proposal through `github-collaboration-setup` by a currently authorized Leader. Whole-file review grants no whole-file ownership: only the exact approved block/resource may change. User prose/link edits or relocation need their own diff/approval. Dirty-edit treatment and Commit ownership are separate choices; a claim/block approval never authorizes staging the whole file.

## Push and Draft PR

Refresh claim successors/conflicts, remote target HEAD/base and changed default-branch authority. Unexpected state stops Push; no force. Inspect existing/proposed Actions triggers and disclose runner/cost uncertainties before the first triggering write. Unknown outcomes need GET before retry; read back a successful Push.

Use `managed_paths.pull_request_template` or applicable project template; explicitly supply body/base/head, preserving prose structure, scope/acceptance/tests/limits/risks/rollback/Actions/remaining work. Create **Draft**, GET URL/number/body/base/HEAD, then fill its actual number in metadata and GET again. Incomplete Draft is not formal pass; never invent its number.

One `agent-collaboration:metadata` HTML comment: JSON `schema_version: 2`, `primary_issue`, `closes_issues`, `actor_id`, `controlled_by`, `controlled_by_id`, `runtime`, `session_id`, `skill_version`, `head_sha`, `base_branch`, `claim_urls`, `workflow: daily` (authorized governance: setup), and mandatory `delivery` below. No duplicate block/key or conflicting identity/version/HEAD. Close numbers: unique positive integers, possibly empty, exactly matching explicit closures. Claim URLs: unique/nonempty/same repository, primary Issue included, actual scope/lineage covered; related claims need not close Issues.

## Fixed delivery and baseline changes

`delivery`: `development_base_sha` equals current effective claim `base_head` (revised value after baseline revision), `net_diff_base_sha`, ordered `predecessors: [{pull_number, head_sha}]`, `merge_order: [predecessor numbers..., this PR]`. Complete fixed SHAs; no predecessor still requires empty `predecessors`/this PR alone in `merge_order`. Development/net-diff bases are separate from default-branch authority.

Any unmerged predecessor permits **Draft only**, both bases equal to last predecessor's fixed HEAD. Verify same-repository order through adjacent fixed-head ancestry, not prose. Closed-unmerged predecessor or fixed-HEAD drift stops delivery. Before Ready/merge all predecessors must be merged; re-fetch actual target SHA as net-diff base, compare complete net diff, recheck claim scope and current-HEAD review/checks. Squash/rebase proves no disappearance; no automatic rebase/force or assumed diff convergence.

Changing claim baseline uses a linked append-only [event revision](event-helpers.md), never silently editing old claims or widening scope. Expanded scope needs separate new claim/preflight. Re-run formal v2 checks after relevant drift; explicit `--legacy-diagnostic` is diagnostic only, never formal pass.

Internal integration is progress, not final default-branch delivery. Its inapplicable final-PR metadata Action is not a required gate there; retain project review/protection and final acceptance.
