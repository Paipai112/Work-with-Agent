# Local configuration: scan, candidate, apply

Use [preflight](preflight-and-identity.md), [authorization](authorization.md) and [managed resources](managed-resources.md). Diagnose/planning is read-only; a project write requires effective Leader or a bounded session and exact action approval.

## Inventory and scope

Resolve verified root/Git state/source SHA and intended paths; `lstat` each component, rejecting symlinks, nonregular files and traversal. Read exact target bytes and tracked/staged/unstaged/untracked state. Existing content belongs to its owner unless exact managed ownership is established. Dirty files need **two choices**: treatment preserving the original bytes (or reviewed merge/defer), and whether those uncommitted edits enter this governance Commit. Duplicate/broken markers, overlapping unmanaged rules or unknown ownership require an explicit choice.

Review complete trusted `managed_paths.entry_files`, including ordinary prose/install links outside blocks; absent list defaults to AGENTS.md/CLAUDE.md/CONTRIBUTING.md. Nested AGENTS.md/CLAUDE.md, AGENTS.override.md and instruction-loading resources are governance. Inspect both rename paths; missing patch retains routing and awaits actual diff. Inspect other paths for reachability effects. Whole-file review grants **no whole-file ownership**: block-external prose/link edits or relocation need their own diff/approval.

Use package verification only when its recorded inputs changed. Inventory each local/remote item with verified previous baseline; authorization registry conflict must be resolved before P/E. Missing baseline never creates an imaginary ancestor.

## Actual configuration candidates

Use actual bundled templates and the existing field-replacement/manual-edit process; no invented generator. Record intended substitutions and final candidate bytes/digest. Before applying/deploying, pass **that exact text** through the same-version checker module's `restricted_yaml` and bundled config/authorization schemas with Draft 2020-12/`FormatChecker()`. Preserve raw text checks before dictionary validation: duplicates, tags, aliases/merges, multi-document and ambiguous values are rejected; supported indented/indentless lists are equivalent.

For a target PR, exercise the real same-version checker CLI with its verified snapshot and record commands/status/limits. Candidates cannot replace trusted default-branch authorization or supply executable check code. Missing deployment/target snapshot remains unverified; first-install bootstrap uses the existing rules and human review, not fabricated PR/approval data. Changing candidate bytes requires revalidation.

For Markdown, `python3 scripts/managed_block.py plan` creates a separate candidate; an exact manual equivalent must preserve every outside byte, BOM/newline style and existing text. Show original/candidate SHA-256 and byte-aware diff. Renderer failure/similar unmanaged rules require a choice, not whole-file rewrite.

## Plan and one-item apply

Keep `operation_id`, verified repository/account/actor/session/mode/source and branch/base/HEAD, template/baseline, exact current/candidate digests, diff, ownership/protection, per-action approvals, completed IDs/read-back and `next_safe_action`; absent files are `absent`, never imaginary empty hashes. The record grants no authority.

Show each resource diff/effect/unknown and approval scope. For a dirty entry show unstaged, staged, candidate and **proposed staged diff**. Get treatment and Commit-ownership choices before writing/staging. An inseparable hunk needs separately reviewed user Commit, verified isolation or deferral: **Do not stage the whole file** without ownership. Exact file approval covers neither Commit/Push/PR nor remote/Actions changes.

Use ownership's **one-item approval/apply loop** with exact stage paths/history preserved. Read back bytes/digest/outside region and surrounding state; mismatch stays unresolved, not automatic replay.

## Project facts and delivery

Populate README pointers from existing requirements/design/decision/progress/validation sources; inspect each, preserve unknowns and one authoritative source per fact, without reconstructing facts or creating empty documents. Retain old role/custom files until a separately approved migration explains preserved content/history.

An integration branch must be registered by default-branch governance before use, with responsible actor/Issue, fixed base and review protections. Use verified permitted base SHA; authority still defaults to trusted branch. For setup create/read back governance Issue and scoped claim, then Issue branch and chosen PR template with one current-HEAD `workflow: setup` metadata block. Partial/internal merges retain final Issues; acceptance/read-back complete delivery.
