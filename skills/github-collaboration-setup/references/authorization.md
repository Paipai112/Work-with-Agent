# Authorization for setup writes

Use after [preflight](preflight-and-identity.md) for `initialize`, `authorization`, `repair`, `upgrade`, or `remote-governance`. A read-only `diagnose` may report missing evidence; it cannot repair it under a Member role. For an initial installation or a lost last Leader, also use [bootstrap and recovery](bootstrap-and-recovery.md).

## Verify format-validation support

Validating authorization records, collaboration events, and other security inputs with `format` fields requires `jsonschema[format]`. Install the validation dependency with:

```sh
python3 -m pip install 'jsonschema[format]>=4.23,<5'
```

Before validation, run this check in the same Python environment that will validate the input. `FormatChecker().checkers` must contain both `uri` and `date-time`:

```sh
python3 -c 'from jsonschema import FormatChecker; missing = {"uri", "date-time"} - FormatChecker().checkers.keys(); raise SystemExit("Missing required format checkers: " + ", ".join(sorted(missing)) if missing else 0)'
```

If the import fails or either checker is absent, treat the input as unverified and stop all writes (fail closed). Do not rely on silently skipped format checks. Continue only after this environment check succeeds and validation passes with `FormatChecker()`.

## Decide the current role

| Verified state | Setup decision |
| --- | --- |
| Account is Admin or Maintain, but Agent has no active delegation and no explicit scoped human session grant | Member; read-only |
| Account permission, repository identity, default-branch SHA, approval evidence, `actor_id`, or an applicable protection rule is unknown/conflicting | Member; stop affected writes and report the missing fact |
| Verified active delegation on the target's default branch, with matching stable account ID and `actor_id` | Leader only within the effective scope below |
| Human grants an eligible actor one explicitly bounded Bootstrap/Recovery session | Session authority only for the named proposal and approved setup steps; it is not yet persistent |
| Delegation revoked, superseded, or directly revoked by the human in the current session | Stop affected writes; retain the record/history |

For a persistent Leader, read `.github/agent-collaboration/config.yml` from the **verified repository's default branch at a recorded commit SHA**, validate it with the bundled `assets/schemas/config.schema.json`, and resolve `managed_paths.authorization`. Read that exact path at the **same recorded SHA**; a custom valid path is authoritative, and a hardcoded fallback or a PR's proposed selector is not. Missing/invalid config, missing selectors, unreadable records and mixed revisions stop authority resolution; use [preflight](preflight-and-identity.md) to distinguish first installation from damaged governance. Validate the active record against the bundled `assets/schemas/authorization.schema.json` with JSON Schema Draft 2020-12 **and `FormatChecker()`**; format-bearing URI and date fields must be checked. The source repository tuple is `hostname`, immutable `repository_id`, `default_branch`, and the record's `default_branch_source_sha`. Check that this provenance SHA was the source revision for the approved governance proposal; the active default-branch SHA after merge is separately recorded read-back evidence. Compare `controlled_by_id` with the authenticated account's stable ID, `controlled_by` with its displayed login, and the responsibility-based `actor_id` with the identity explicitly selected for this session. Reject an unapproved PR-branch copy, a local working file, `granted_by` text alone, a malformed schema, or a record for another repository. If the default branch is unprotected, disclose its tamper-resistance gap.

For v0.1, the configured protocol, authorization and managed-resource files must stay inside `.github/agent-collaboration/` as normalized repository-relative POSIX paths, without empty, dot, parent or symlink components. Custom filenames within that directory are supported; relocating the governance root is not. Report any existing incompatible path and propose a reviewed repair; never silently move files or select a fallback.

Every setup write requires the intersection of:

```text
active Leader delegation or current scoped Bootstrap/Recovery session
∩ frozen permission_ceiling
∩ freshly queried GitHub account permission
∩ project protocol's allowed governance scope
∩ existing Rulesets and branch protection
∩ human approval for this exact change and action
```

Apply the target's actual existing and inherited protections; server enforcement is optional, not a prerequisite for installing persistent authorization. Disclose verified unsupported enforcement or an unprotected branch's tamper-resistance gap while retaining protocol review and explicit human approvals. An unsupported endpoint or capability does not prove that applicable protections are absent. If identity or any applicable rule remains unreadable, unknown, or conflicting, stop affected writes; preserve every known stronger gate.

Permission order is `read < triage < write < maintain < admin`; a setup mutation still requires a valid Leader or scoped session, even if the numerical intersection is `write` or higher. Requery account permission and the default-branch authority before each governance action, formal review, and merge. A successful earlier check is not authorization after identity, source SHA, target HEAD, or protection state changes. Never let a proposed PR edit to authorization, schema, or checker decide its own eligibility: evaluate under the existing default-branch rules through merge.

## Grant and ceiling decisions

| Change | Required decision |
| --- | --- |
| Promote a Member to Leader | Human explicitly names the `actor_id`, controlling account, repository, and ceiling; the target account has verified Maintain or Admin. An existing effective Leader submits a separate governance PR under the old rules. |
| Account Maintain becomes Admin | Keep the prior Maintain ceiling. Ask for a new human authorization and governance PR if Admin scope is actually needed. |
| Account Admin becomes Maintain, Write, or lower | Reduce effective permission immediately to the current account permission; a lower-than-Maintain account cannot perform Leader setup writes. |
| Raise a delegation ceiling | User explicitly approves this exact ceiling and PR; target ceiling cannot exceed target account's current permission or the executing Leader's effective ceiling. |
| Maintain Leader seeks Admin ceiling | Existing Maintain Leader cannot grant it. A human controlling an Admin account may explicitly authorize a session confined to this escalation proposal; it cannot approve its own expanded record. |
| Revoke a delegation | Human instruction to the current Agent takes effect immediately. Persist revocation through a separate governance PR that marks the old record `revoked`, retaining audit history. Other sessions stop after fresh preflight; shared GitHub credentials require human account/credential action for immediate universal cut-off. |

Authorization changes are explicit governance review, outside generic automatic whole-file resource upgrades. Before preparing `P` or `E`, resolve any existing registry ownership conflict through [managed resources](managed-resources.md); retain the authorization records and audit history.

An `active` persistent record includes an `approval_evidence` object with the governance PR URL, human `approved_by`, `approved_at`, and **`approved_head_sha`**. This field records the human-approved governance **content proposal** HEAD `P`; it cannot name its own containing commit. Add/update that evidence in a subsequent commit `E`, then compare `E` with `P`: only the `approval_evidence` fields may differ. Obtain a separate auditable human GitHub Review or equivalent documented approval of the final `E` HEAD, applying any protection rule that dismisses old reviews. Verify the authentic human approver, repository/PR, exact `E` SHA, approved scope, and read-back evidence outside the authorization file. Equivalent approval satisfies the final human authorization approval only; protocol review must still be independently satisfied, and an existing native review requirement still needs an eligible review from another account. The PR author's account cannot supply its own native Approve. If content, scope, or ceiling changes after `P`, restart content approval and the evidence-only step. Do not put `E`'s SHA or the merge SHA back into the same file; retain final approval, merge SHA, and default-branch read-back as external evidence. Do not treat proposed `status: active` as current authority before merge and read-back.

## Request and evidence shape

Before asking the human to grant or change authorization, show the verified repository host/ID/owner/name/default branch/source SHA; the current account login/ID/permission; proposed `actor_id` and ceiling; exact authorized setup scope and session lifetime; the current active delegations and protections; and the proposed file diff or PR HEAD. Record approval against those values. The session cannot be transferred to a different actor, account, repository, branch, source SHA, proposal, or later run by reusing chat history. If interrupted, re-establish identity and obtain a fresh scoped confirmation.

For a persistent proposal, inspect the proposed fields at `P` against the schema requirements **except the not-yet-available approval evidence**; `P` is an incomplete draft and must not merge. Obtain content approval for `P`, create evidence-only `E`, and validate the **complete `E` record** with Draft 2020-12 and `FormatChecker()`. Verify the separate external final approval for `E` as specified above, and query GitHub's current review state for every applicable native requirement. Merge only after all existing GitHub and protocol gates pass. At the post-merge default-branch SHA, re-read config and its configured authorization path together, validate both, and compare repository/account/actor/ceiling/status and `approved_head_sha=P` to the approved content proposal. Also preserve the external approval of final `E`. Only then report a persistent Leader. A local plan or resume record is not an authorization source.
