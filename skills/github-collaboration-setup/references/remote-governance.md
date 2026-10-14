# Remote governance

Use [preflight](preflight-and-identity.md), [authorization](authorization.md), [ownership](managed-resources.md), and [Actions/protection](actions-and-rulesets.md) when relevant. Diagnose is read-only. Check live [GitHub REST docs](https://docs.github.com/en/rest) for host/version/plan and exact endpoint rights; account Admin/Maintain alone is insufficient.

Use ownership's **one-item approval/apply loop**, binding exact endpoint rights and trigger/cost uncertainty. Same name is never ownership.

## Resource-specific contracts

| Resource | Discovery and stable identity | Proposal/apply/read-back |
| --- | --- | --- |
| Label | Paginated `repos/OWNER/REPO/labels`; numeric ID/node_id and current name | Issues/Pull requests write capability; approve name/color/description only. POST verified absent or PATCH registered name, then verify returned numeric ID and fields; no Issue “set labels” |
| Issue Form/chooser | Default-branch `.github/ISSUE_TEMPLATE/` files and config.yml; repository+path, source/blob SHA | Preserve existing templates/chooser/comments; approve exact governance file diff and separately Commit/Push/PR; after merge GET default bytes and chooser |
| PR template | Trusted `managed_paths.pull_request_template`; if absent list root/docs/.github default and multi-template candidates, then ask exact path | Issue chooser config does not select PR templates. Approve file and any selector diff; web uses `template` query, CLI/API explicit chosen-file body. GET selector/file at same default SHA, verify selected path and subsequent body |
| Workflow | Default-branch path/bytes and prior baseline; workflow ID when available | Approve YAML, trigger/runner/token/dependency diff; Actions approval precedes any trigger. After merge GET trusted bytes and actual run/check at expected SHA |
| CODEOWNERS | Active search location, all candidates, path/blob SHA and eligible users/teams | Preserve order; show actual per-path last-pattern ownership changes. Approve them separately, then GET active file/owners; native CODEOWNER review has a distinct other-account prerequisite |
| Actions setting | actions/permissions and actions/permissions/workflow plus organization policy; repository+endpoint | Effective Admin ceiling and endpoint Administration write. Approve only selected enablement/allowed-actions/token fields; GET same endpoint and inherited policy afterward |
| Required Check | Effective branch/Ruleset plus successful trusted current-SHA check context/source App ID | Effective Admin/actual rules right. Approve addition separately **after real successful run**; retain existing checks, GET effective rule and representative PR merge requirements |
| Ruleset | Paginated `rulesets?includes_parents=true`, GET numeric ID/source and effective `rules/branches/BRANCH` | Effective Admin/custom edit-rules plus endpoint right. POST verified absent; registered repository ID updates use **PUT** 完整 current preservation-safe object, including complete conditions/rules/bypass_actors arrays. Approve changed fields, preserve unowned/inherited state; unreadable fields stop. GET ID and effective rules |
| Branch protection | branches/BRANCH/protection plus effective rules; repository+exact ref/endpoint | Effective Admin/Administration write and feature support. Approve every affected field; required PUT fields/null semantics demand a full preservation-safe payload. GET full protection/effective rules; uncertainty stops |

Organization Rulesets require separate organization authority; repository ownership cannot claim them. No partial bundled template may replace a complete remote object.

New native reviews/CODEOWNER/check requirements additionally load Actions/protection's satisfiability gates; do not weaken existing requirements.

Runtime primary references: [Labels](https://docs.github.com/en/rest/issues/labels), [templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates), [PR selection](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository), [Actions settings](https://docs.github.com/en/rest/actions/permissions), [Rulesets](https://docs.github.com/en/rest/repos/rules), [branch protection](https://docs.github.com/en/rest/branches/branch-protection).
