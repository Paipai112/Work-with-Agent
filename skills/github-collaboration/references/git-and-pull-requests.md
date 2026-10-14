# Issue-linked Git and Draft PR work

Use [preflight](preflight.md) and [current claim verification](claims-and-handoffs.md). Implementation/Git writes require an open Issue and a read-back-verified uncontested claim covering account/actor/session, branch and exact changed scope. Review does not take the implementer's claim.

## Branch and local changes

- Use `agent/<actor_id>/issue-<primary_issue>-<description>` from a verified default-branch SHA or a trusted-config `branch_policy.integration_branches` SHA (absent list means empty). Integration branches use the same naming. Record actual base/ref/SHA; local `main` is not verified. Authority always comes from the default branch.
- Inspect status, unstaged/staged diff, untracked paths and old/new rename paths against claim scope. Preserve user work; inseparable/conflicting edits need an explicit choice. Validate intended changes and inspect filenames/content for credentials and unrelated generated output without printing secrets.
- Stage inspected exact paths with `git add -- <paths>`; no `git add .`, globs or unscoped `git add -A`. Scoped `git add -A -- <paths>` requires explicit project permission; this project's template forbids every form. Review full cached diff, name/status and `--check` before Commit. Record Issue/actor and real tests; never rewrite another Agent's history or commit daily work on the default branch.

## Governance separation

Compare full changed-file scope and actual diff with trusted managed paths before stage/Commit/Push/Ready. Protocol/config/authorization/registry/schema/checker/templates/workflows/settings and instruction-loading resources are governance. **Complete** registered `managed_paths.entry_files` are governance, including ordinary prose or links outside their block; absent registration defaults to AGENTS.md/CLAUDE.md/CONTRIBUTING.md. Nested AGENTS.md/CLAUDE.md and AGENTS.override.md also qualify. Inspect both rename paths. Missing patch never grants an exemption; obtain the actual diff for approval. Inspect other paths for entry/install-link reachability effects; the checker is a conservative path classifier, not a proof about arbitrary prose.

Keep business work Draft and route a separate governance proposal through `github-collaboration-setup` by a currently authorized Leader. Whole-file review grants no whole-file ownership: only the exact approved block/resource may change. User prose/link edits or relocation need their own diff/approval. Dirty-edit treatment and Commit ownership are separate choices; a claim/block approval never authorizes staging the whole file.

## Push and Draft PR

Refresh claim successors/conflicts, remote target HEAD/base and changed default-branch authority. Unexpected state stops Push; no force. Inspect existing/proposed Actions triggers and disclose runner/cost uncertainties before the first triggering write. Unknown outcomes need GET before retry; read back a successful Push.

Read the configured `managed_paths.pull_request_template`, or applicable project template, and construct the explicit body/base/head; do not assume GitHub fills it. Keep its prose structure and include scope/acceptance, real validation, limits, risks/rollback, Actions notice, remaining work/handoff. Create **Draft** and GET its URL/body/base/HEAD.

Exactly one `agent-collaboration:metadata` HTML comment contains JSON fields: `schema_version: 1`, `primary_issue`, `closes_issues`, `actor_id`, `controlled_by`, `controlled_by_id`, `runtime`, `session_id`, `skill_version`, `head_sha`, `base_branch`, `claim_urls`, `workflow: daily` (setup only for authorized governance). No duplicate block/key or conflicting identity/version/HEAD. Close numbers are unique positive integers, possibly empty; explicit closures agree exactly. Claim URLs are unique/nonempty, same repository, include the primary Issue and cover actual scope/lineage; related claims need not close their Issues.

Internal integration is progress, not final default-branch delivery. Its inapplicable final-PR metadata Action is not a required gate there; retain project review/protection and final acceptance.
