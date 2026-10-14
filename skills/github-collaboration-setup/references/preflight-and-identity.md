# Setup preflight and identity

Read [session core](session-core.md). Use this package's `assets/schemas/config.schema.json` and `assets/schemas/authorization.schema.json` with Draft 2020-12 and `FormatChecker()`. Shared gates preserve default-branch identity, same-SHA selectors, role/ceiling, task scope and conditional [package verification](package-verification.md).

Inventory local Git state, intended paths and existing project requirements/design/decision/progress/validation pointers. Query current protection, Rulesets, required reviews/checks, Actions and managed resources relevant to this proposal; inaccessible facts remain unknown. Config absence, missing authorization, revoked last Leader and unreadable/damaged installation are distinct states. A first install chooses paths in a reviewed Bootstrap proposal; damage cannot be turned into Bootstrap by deleting history.

Select one setup mode and responsibility/account. Diagnose ends with findings, gaps and next safe action. A write continues through [authorization](authorization.md) and its mode procedure, with current delegated/session scope and exact approval.

If prerequisites are absent, keep completed resources and disclose the missing step: no account → [GitHub signup](https://github.com/signup); no authentication → browser `gh auth login --web`; no Git/remote/repository → separately approve Git init, host/owner/name/visibility and creation, minimal initial Commit, and Push through [Bootstrap](bootstrap-and-recovery.md). Never request a token in chat or print it. A verified Maintain/Admin account is required for a scoped setup grant; account permission alone grants none. Existing history never uses the minimal first-commit exception.
