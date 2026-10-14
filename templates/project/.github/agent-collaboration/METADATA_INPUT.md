# PR 元数据采集与检查输入

本文件是 v0.2 本地候选合同，尚未发布或启用 Actions。在线入口使用消费项目默认分支同一 SHA 的完整检查链；pass 仅表示当前快照的元数据检查通过，不是写入或合并授权。

## 一、运行入口

准备 Python 3.11+、已登录目标账号的 `gh` 和内容/PR/Issue 读取权限。collector/launcher 为标准库，checker 的事件验证另需 `requirements-helpers.txt` 声明的 PyYAML/jsonschema；本地由操作者显式准备，程序不自动 pip。所有 GitHub 请求均为 GET。

```sh
python3 .github/agent-collaboration/run_pr_metadata_check.py \
  --repository owner/repository --pull-number 12 --output-dir metadata-output
```

这条命令会输出一个 JSON 报告，并在指定目录保存 `metadata.json` 和 `check-report.json`。不传 `--output-dir` 时使用临时目录，退出后清理本次临时文件。

输出目录必须是新目录或空的普通目录，且路径及父组件不能是 symlink，也不能包含 `..`。既有目录被占用时，在写入输出前返回 unknown，保留原字节；每次保存快照请选择新目录。checker 的工作目录始终是本次临时目录，产物通过排他创建写入指定目录。

持久输出要求系统支持目录描述符、`O_DIRECTORY`、`O_NOFOLLOW` 和相对描述符操作；能力缺失时返回 unknown，不能降级为跟随路径写入。可不传 `--output-dir` 使用临时检查并读取标准输出。Windows 原生运行本轮未验证。

- 仅保存采集输入：给上述入口增加 `--collect-only`；标准输出为 payload JSON，不提供 checker 的 pass。
- 直接采集：`python3 .github/agent-collaboration/collect_pr_metadata.py --repository owner/repository --pull-number 12`；这个入口通过同目录启动器定位并运行可信部署副本。
- 绑定外部已核实目标：可提供 `--repository-id`、`--expected-head` 和 `--expected-trusted-sha`；程序仍独立 GET 核验，参数不会替代在线证据。
- Actions 适配：工作流增加 `--default-target-only`，只检查以当前默认分支为目标的 PR。本地入口可交给 checker 核验配置登记的集成分支目标。

本地启动器必须与已核验默认 SHA 上的部署版本字节一致。不一致时返回 unknown，并提示从该 SHA 更新启动器；不会把本地邻近的 checker 或 collector 当成正式权威执行。

## 二、输入结构

配置/授权为 UTF-8 原文；评论正文保留原始换行。

正式 v0.2 PR metadata 使用 `schema_version: 2`，保留原字段并增加必填 `delivery`：

```json
{
  "development_base_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "net_diff_base_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "predecessors": [{"pull_number": 10, "head_sha": "cccccccccccccccccccccccccccccccccccccccc"}],
  "merge_order": [10, 12]
}
```

- `development_base_sha` 等于当前有效 claim 的 `base_head`；baseline revision 后填写修订后值，与授权来源 `trusted_sha` 分开。
- `net_diff_base_sha` 是固定净 diff 的比较基线。前置未合并时为最后一个前置的固定 HEAD；最终阶段为当前 PR 的实际 base SHA。
- `predecessors` 按交付先后登记同仓前置 PR 与固定 HEAD；`merge_order` 必须依次包含这些 PR，最后是当前 PR。程序还核验实际前置关系，不能只依赖正文顺序。
- 无前置时保留该结构，使用空 `predecessors` 和仅含当前 PR number 的 `merge_order`。

collector 输出 `predecessor_pulls`（按声明顺序的 PR 原对象）、`predecessor_files`（number 字符串→完整分页文件）、`development_compare`、`net_diff`、`predecessor_compares`。后三者使用固定比较结构：`base_sha`、`head_sha`、`merge_base_sha`、`status`、完整分页 SHA 列表 `commits`、`files`、`complete: true`。`predecessor_compares` 依次绑定相邻前置固定 HEAD，长度为前置数减一（无前置为零），据实际祖先关系核验顺序。采集结束前二次 GET 全部事实；`complete` 不是签名，离线输入可被改写。

基线修订追加 `event: claim` 并引用前驱，局部 `revision` 为：`schema_version: 1`、`kind: baseline`、原始根 `original_event_id`/`github_comment_id`/`github_comment_url`/`old_body_sha256`、非空 `reason`、`from_base_head`、`to_base_head`。from 等于前驱有效基线，to 等于新 claim 基线；身份、session、branch、scope 不变。`kind: correction` 不得改基线。范围变化需单独有效认领与预检，不能事后补授权。

尚有未合并前置时只检查 Draft：两基线均为最后前置固定 HEAD；总 API diff 必须由实际前置文件与当前净增量解释，当前净文件必须在当前 claim scope 内。继承的 added 与净 modified 不要求状态相等。全部前置合并后净基线必须是当前 PR target SHA，API/net 的路径、状态、rename 新旧元组一致并过 scope。关闭未合并、固定 HEAD 变化拒绝；无法安全解释返回 unknown。squash/rebase 不默认收敛：在当前基线重验净 diff/scope，需修订时追加上述事件；旧审核无效，不自动 rebase/force。

| 字段 | 内容 |
| --- | --- |
| `trusted_ref_verified` | 官方入口验证当前默认分支后写入的 `true` |
| `trusted_sha` | 已核验默认分支的完整 40 位 SHA |
| `repository` | 稳定 `id`、`full_name`、`default_branch` |
| `pull` | GitHub PR 原始对象，包含实际 HEAD、base、作者与正文 |
| `files` | 完整分页的变更文件记录，保留重命名信息 |
| `reviews` | 完整分页的 GitHub 审核记录 |
| `issues` | 主 Issue、关闭引用与 claim 引用涉及的全部 Issue 对象 |
| `config` | 同可信 SHA 的配置原文 |
| `authorization` | 由配置 `managed_paths.authorization` 指定、同可信 SHA 的授权原文 |
| `claim_comments` | 规范 claim URL 到评论记录的映射；已确认不存在时为 `null` |
| `issue_comments` | 十进制 Issue number 字符串到该 Issue 完整评论记录列表的映射 |
| `snapshot` | v2 来源与采集时点记录 |

`claim_comments` 与 `issue_comments` 的评论记录使用同一结构：

```json
{
  "id": 1,
  "url": "https://github.com/owner/repository/issues/7#issuecomment-1",
  "user_id": 1001,
  "login": "developer",
  "issue_number": 7,
  "body": "原始评论正文，保留换行",
  "updated_at": "2026-10-14T00:00:00Z"
}
```

- 评论实际 ID、URL、所属 Issue 和作者稳定 ID 来自 GitHub 返回对象，并核对其来源关系。
- 完整 Issue 评论保留 release、handoff、reassign、resume 和其他后续事件的原文；采集器不解释这些事件的授权效力。
- claim 单条读取与完整评论列表不一致时，要求重新采集，不能拼接成完成快照。

`snapshot.version=2`、`check_contract=2`、`source=github-get`，记录 `collected_at`/`verified_at`、仓库 ID、默认分支、可信 SHA、PR number、HEAD SHA、base ref；`trusted_resources` 保存完整部署资源的 SHA256/字节数。

`unverified` 包含真人批准、实时权限、原生保护/Required Reviews、Skill 加载、协议当前 HEAD 审核、未列 Issue 冲突、历史每步写入授权和旧进程终止。只收相关 Issue，不扫全仓；已知活跃冲突拒绝，不能据 pass 宣称全仓独占。重分配需结构有效的可信 Leader 委派、精确目标与继任 claim；旧进程 unknown 时必须独立分支。没有 native APPROVED 不自动失败；已有审核必须适用于当前 HEAD 与合并/基线修订后内容。协议职责独立不等于另一个账号，合并门禁仍须 Agent/真人核验。

## 三、可信部署与刷新

固定资源均在 `.github/agent-collaboration/` 同目录：`run_pr_metadata_check.py`、`collect_pr_metadata.py`、`check_pr_metadata.py`、`collaboration_event.py`、`collaboration_scope.py`、`collaboration-event.schema.json`、`requirements-helpers.txt`、`config.yml`，另加配置指定的授权文件。helper/schema/requirements 来自唯一 shared/schema 规范源，由 setup 包映射部署，不手工生成另一套解释器。资源须在同 SHA Git 树中是唯一普通 blob，字节同时匹配树与 Contents blob SHA；symlink/gitlink、歧义、截断或超过 262144 字节均 unknown。

`COLLECTOR_INPUT_VERSION`/`INPUT_VERSION=2` 仅握手输入封装；`FORMAL_CHECK_VERSION`/`CHECK_CONTRACT_VERSION=2` 与 snapshot.check_contract 另握手本轮事件/交付检查。缺一、资源/依赖缺失或不匹配不能正式 pass。将来新增资源须显式扩展固定表、setup 映射与握手，不能任意动态加载。Actions 候选从同 SHA 校验 requirements 后显式创建临时 venv、pip 准备依赖，再调用相同入口；本轮只模拟该 OS 边界，未启用远端执行。

采集结束前再次 GET 仓库身份、默认分支 SHA、PR HEAD/base/body、相关 Issue、完整评论及审核。变化时返回 unknown 并要求重采集。这个复核不能保证采集结束后没有变化；合并前仍须读取当时的目标与审核事实。

## 四、结果与错误

| 模式或结果 | 退出码 | 含义 |
| --- | --- | --- |
| collect-only 成功 | `0` | 输出完整 payload；没有 checker 判定 |
| 正式 `result: pass` | `0` | checker 完成并通过当前快照的声明检查 |
| 正式 `result: fail` | `1` | checker 完成，快照存在可核验的拒绝项 |
| `result: unknown` | `2` | 来源、完整性、时点或执行证据不足；不能提供完成快照或正式检查结论 |

离线 checker `python3 .github/agent-collaboration/check_pr_metadata.py INPUT_JSON OUTPUT_DIR` 输出 `RESULT=pass/fail/unknown`，仅对该快照结构与字节一致性负责，不证明实时来源。旧输入只能显式加 `--legacy-diagnostic`，输出 `LEGACY_RESULT=pass/fail`（退出 0/1）；删除 snapshot 不会获得正式 pass。在线 launcher 只接受完整 v2。

unknown 的标准输出为 JSON，包含 `errors` 与 `snapshot: null`。GitHub 原始错误和凭据不回显。

- files 达到 GitHub 3000 条上限，或 `changed_files` 与取得数量不一致时，拒绝可能截断的列表。
- 每页请求 100 条；连续 31 个满页、重复文件路径或审核/评论 ID 会使分页证据不足。
- [GitHub Compare API](https://docs.github.com/en/rest/commits/commits#compare-two-commits) 的 files 只在第一页且最多 300 条；达到 300 即 unknown，不假装分页文件完整。提交须完整分页、最后 SHA 绑定固定 HEAD，两次比较一致。
- 不可读资源、限流、超时、部署版本不匹配和 checker 未正常给出兼容结果均返回 unknown。
- 工作流文件是可选部署候选；该模板的模拟验证不启用远端 Actions，也不证明 Required Checks 或服务端审批已经生效。
