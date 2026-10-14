# Actions and server protection

Use with [remote governance](remote-governance.md). Inventory is read-only; writes need current role/scope, actual endpoint rights and individual approval. GitHub cannot prove Skill loading or distinguish actors sharing one account.

## Before first possible trigger

Inspect proposed **and existing** workflows matching Push/PR/update/merge/dispatch before that write. Show exact YAML/filters/events, runner/OS, steps/dependencies pinned by SHA, token permissions, secrets/environments/caches and trusted/untrusted inputs. Display repository visibility, organization policies, expected runs/minutes/storage/cache effects and billed owner. Consult current plan/usage/budget and [billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) before numerical claims; unavailable cost is an explicit approval uncertainty. Public/private/standard/larger/self-hosted runners differ.

Bind separate execution approval to repository, workflow/settings digest, trigger/runner, operation and current SHA. Without it stop before first trigger, not afterward. A workflow-free alternative is a new file proposal and still must inspect existing triggers. Execution approval enables no repository setting.

## Trusted metadata boundary

Formal metadata collection/checking uses consumer default-branch config/authorization/collector/checker at the same verified SHA; installed copies only reuse byte-matched trusted deployment. Never execute candidate PR programs/schema/dependency commands, interpolate untrusted text into shell or share privileged secrets/caches with product tests. `pull_request_target` is limited to this reviewed nonexecuting path; host policy may prohibit it. Product-code CI needs its own approved low-permission isolation.

The final-PR metadata job targets actual default branch only. Registered integration targets may show skipped jobs without runner allocation; skipped is not success and that inapplicable check must not be required there. Integration authorization remains default-branch based.

First bootstrap cannot trust its own proposed workflow. Use old rules/human and local validation, then merge/read back trusted workflow and observe a representative real run URL, SHA, context/source and result. Required Check is a later separate proposal. Verify normal updates and merge queue `merge_group` if used; filters/skips/cancellations cannot silently leave required contexts absent/stale or dependent on their own success.

## Satisfiable gates and preserved rules

Before Required Check, prove successful trusted context/source on relevant SHA and update/event coverage; approve exact context/App addition, preserve existing contexts, GET rule and PR merge requirements. No real run means defer.

Before new native review/CODEOWNER requirements, prove another eligible account can review representative PRs and owners/teams have required access; evaluate visible teams and last-pattern precedence. Shared-account protocol comments are not native Approve. Missing second account defers new gates, never weakens existing ones.

GET all paginated/inherited Rulesets, numeric ID/source_type/source/target/enforcement/conditions/rules/bypass actors, and effective branch rules/protection. Hidden bypass fields are unknown, not empty. Same-name/no-baseline requires explicit ownership choice. Admin/custom edit-rules, Administration write, host/plan availability and organization authority are separate checks.

Show full effective before/after refs, PR/reviewer/CODEOWNER/conversation/check/source/history/force/deletion/bypass policy. Preserve every stronger gate; union/inheritance may be stricter. Apply only through remote governance's complete preservation-safe PUT/read-back contract, never a partial template or unknown-field overwrite. Network ambiguity queries exact resource before retry. 2xx, templates and unavailable endpoints do not prove enforcement.

Live primary references: [events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target), [checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks), [reviews](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request), [CODEOWNERS](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), [Ruleset API](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset).
