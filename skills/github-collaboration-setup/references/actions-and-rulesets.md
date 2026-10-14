# Actions and server protection

Use [remote governance](remote-governance.md) for ownership/endpoint rights/individual approval. Inventory is read-only; GitHub proves no Skill loading or shared-account actor distinction.

## Before first possible trigger

Before Push/PR/update/merge/dispatch inspect proposed **and existing** matching workflows: exact YAML/filters/events/runner/OS/SHA-pinned steps/dependencies, token permissions/secrets/environments/caches/input trust. Show visibility/org policy/runs/minutes/storage/cache/billed owner; verify current plan/usage/budget/[billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) before numbers. Unknown cost needs explicit uncertainty approval; runner/visibility classes differ.

Separate execution approval binds repository/workflow-settings digest/trigger/runner/action/current SHA **before** first trigger. Workflow-free proposal still checks existing triggers; execution approval enables no setting.

## Trusted metadata boundary

Formal metadata uses same verified consumer-default SHA config/authorization/collector/checker; installed copies must byte-match deployment. Never execute candidate PR program/schema/dependencies, interpolate untrusted shell text or share privileged secrets/caches with product tests. `pull_request_target` only uses this reviewed nonexecuting path, if host allows; product CI needs approved low-permission isolation.

Final metadata job targets actual default only. Integration may skip without runner; skipped ≠ success, and this inapplicable check must not be required there. Authority remains default based.

Bootstrap cannot trust its proposed workflow: old rules/human/local validation, then merge/GET trusted workflow and real run URL/SHA/context/source/result. Required Check is separately approved later. Verify updates/used `merge_group`; filters/skips/cancellations/self-dependency must not leave required contexts absent/stale.

## Satisfiable gates and preserved rules

Required Check needs real successful trusted context/source/relevant SHA/event coverage, exact context/App approval, preserved existing contexts, GET effective rule/PR requirements; no real run means defer.

New native review/CODEOWNER gates need eligible other-account representative review, owner/team access/visibility/last-pattern verification. Shared-account comments are not native Approve; missing account defers new gates, never weakens existing ones.

GET paginated/inherited Rulesets: ID/source_type/source/target/enforcement/conditions/rules/bypass actors/effective branch protection. Hidden bypass ≠ empty. Same-name/no-baseline needs ownership choice. Separately verify Admin/custom edit-rules, Administration write, host/plan/org authority.

Show full effective before/after refs/PR/reviewer/CODEOWNER/conversation/check/source/history/force/deletion/bypass; preserve stronger/inherited gates. Use remote governance's complete preservation-safe PUT/GET, no partial template/unknown-field overwrite. Unknown result queries before retry; 2xx/template/unavailable endpoint proves no enforcement.

Live primary references: [events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target), [checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks), [reviews](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request), [CODEOWNERS](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), [Ruleset API](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset).
