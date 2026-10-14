# Bootstrap and lost-Leader recovery

Use [preflight](preflight-and-identity.md) and [authorization](authorization.md). These session grants cover named governance setup/repair only; daily may be absent, but ordinary development still requires it.

## Eligibility

| Observed state | Route |
| --- | --- |
| Account below Maintain/unknown | Read-only; request an eligible human/account |
| Existing repository with no installed authorization; verified Maintain/Admin | Human may explicitly grant a bounded Bootstrap session to this account/actor/repository/source SHA |
| Active Leader exists | Use its current delegation; no Bootstrap shortcut |
| Existing authorization lost/revoked/unreadable | Inspect old rules/history; eligible human grants scoped Recovery, not a fabricated first install |
| Git/remote/repository absent | Separately approved creation sequence below; proposed identity is not permission |

## Establish a new repository

1. Inventory target/files/secrets without printing values. Show host/owner/name/visibility and named actor; any Bootstrap intent is conditional until repository ID and source SHA exist. Missing account/authentication uses preflight's secure login route.
2. Obtain separate approval for Git init, remote repository creation, minimal initial Commit and Push. Preserve existing history. After creation GET ID/URL/visibility/default-branch state, authenticated stable account and actual permission; below Maintain/unknown stops setup while retaining and reporting the created resource.
3. If no default commit exists, show exact path manifest and credential/large/generated-file scan; an empty Commit is valid. Exclude governance/workflows/authorization and unapproved user edits; use exact stage paths, never stage-all. Only this approved minimal branch-establishing Commit may go directly to default branch. Existing history/protection never takes this exception.
4. GET actual default branch/source SHA, permission and protection; have the human reconfirm Bootstrap as a bounded effective grant for these verified values and a named proposal. Creation approval/earlier intent grants no setup role. Blocking rules stay in force.

## Governance and persistence

Create the governance Issue and first scoped claim, capture/read back its URL, then use an isolated Issue branch from verified default SHA. First Issue/claim needs no previous implementation claim. Build local candidates through [local configuration](local-configuration.md), using selected authorization path (or explicitly approved first-install selector), identity and human-approved ceiling.

Approve file diffs, Commit, possible Actions, Push and PR as separate actions. Use the chosen project template with one current-HEAD `workflow: setup` metadata block. Keep actual reviews/checks/CODEOWNERS/protection; absent reviewers leave a pending PR.

Follow authorization's complete **P → evidence-only E → external final-E approval → old-rule/SHA-locked merge → same-SHA read-back** chain, registry conflict resolved first. Candidate `active` grants nothing; only verified read-back activates persistent Leader, failure retains Member/session. Interruption/identity/source/proposal drift needs fresh session confirmation.

## Recovery or Admin escalation

Read the configured authorization and old protocol at verified default SHA; distinguish revoked/superseded/missing/unreadable records. Preserve files/history: deleting/renaming authorization cannot manufacture Bootstrap. A human controlling verified Maintain/Admin explicitly binds Recovery to account/actor, ceiling, exact proposal/actions and this-session expiry.

Independent governance retains old records/status history and all existing gates/activation chain; Recovery waives no missing reviewer. Human Admin escalation is confined to the named ceiling PR; Maintain Leader cannot approve its own expansion.
