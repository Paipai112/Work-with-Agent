# PR 元数据采集与检查输入

本地正式检查和 Actions 使用消费项目默认分支同一 SHA 上的采集器、checker、配置和授权文件。采集完成仅表示取得了当前快照；正式检查的 pass 表示该快照通过 checker 的声明检查。

## 一、运行入口

准备 Python 3.11+、已登录目标 GitHub 账号的 `gh`，以及仓库内容、PR 和 Issue 的读取权限。采集器与启动器使用 Python 标准库，所有 GitHub 请求均显式为 GET。

```sh
python3 .github/agent-collaboration/run_pr_metadata_check.py \
  --repository owner/repository --pull-number 12 --output-dir metadata-output
```

这条命令会输出一个 JSON 报告，并在指定目录保存 `metadata.json` 和 `check-report.json`。不传 `--output-dir` 时使用临时目录，退出后清理本次临时文件。

- 仅保存采集输入：给上述入口增加 `--collect-only`；标准输出为 payload JSON，不提供 checker 的 pass。
- 直接采集：`python3 .github/agent-collaboration/collect_pr_metadata.py --repository owner/repository --pull-number 12`；这个入口通过同目录启动器定位并运行可信部署副本。
- 绑定外部已核实目标：可提供 `--repository-id`、`--expected-head` 和 `--expected-trusted-sha`；程序仍独立 GET 核验，参数不会替代在线证据。
- Actions 适配：工作流增加 `--default-target-only`，只检查以当前默认分支为目标的 PR。本地入口可交给 checker 核验配置登记的集成分支目标。

本地启动器必须与已核验默认 SHA 上的部署版本字节一致。不一致时返回 unknown，并提示从该 SHA 更新启动器；不会把本地邻近的 checker 或 collector 当成正式权威执行。

## 二、输入结构

payload 保留旧主字段，并增加 `issue_comments` 与 `snapshot`。配置和授权保存为原始 UTF-8 文本，使 checker 能检查原始 YAML 语法。

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

`snapshot.version` 为 `2`，`source` 为 `github-get`。其中记录 `collected_at`、`verified_at`、仓库 ID、默认分支、可信 SHA、PR number、HEAD SHA、base ref；`trusted_resources` 以部署路径为 key 保存每个资源的 SHA256 和字节数。

`snapshot.unverified` 明确列出本检查未证明的真人批准、实时账号权限、GitHub 原生分支保护与实际 Skill 加载。离线 JSON 的来源标记可由文件编辑者改写；离线 checker 结论仅适用于该输入，正式来源核验须通过在线可信入口完成。

## 三、可信部署与刷新

启动器的固定程序资源表为 `TRUSTED_PROGRAM_FILES`，当前列出：

- `.github/agent-collaboration/run_pr_metadata_check.py`
- `.github/agent-collaboration/collect_pr_metadata.py`
- `.github/agent-collaboration/check_pr_metadata.py`

启动器还从同 SHA 读取 `config.yml` 和配置指定的授权文件。每个资源须在同 SHA 的 Git 树中是唯一普通 blob，内容字节须同时匹配 Git 树与 Contents API 的 blob SHA；symlink、gitlink、歧义路径、截断树和超出 262144 字节的资源均返回 unknown。

`COLLECTOR_INPUT_VERSION = 2` 与采集器的 `INPUT_VERSION = 2` 是输入封装兼容握手。该常量只确认同一输入结构，不证明 checker 已实现新事件或叠加交付的判断。增强检查器所需 helper、schema 和依赖必须明确进入固定部署资源表；缺失或不匹配时不能提供正式 pass。

采集结束前再次 GET 仓库身份、默认分支 SHA、PR HEAD/base/body、相关 Issue、完整评论及审核。变化时返回 unknown 并要求重采集。这个复核不能保证采集结束后没有变化；合并前仍须读取当时的目标与审核事实。

## 四、结果与错误

| 模式或结果 | 退出码 | 含义 |
| --- | --- | --- |
| collect-only 成功 | `0` | 输出完整 payload；没有 checker 判定 |
| 正式 `result: pass` | `0` | checker 完成并通过当前快照的声明检查 |
| 正式 `result: fail` | `1` | checker 完成，快照存在可核验的拒绝项 |
| `result: unknown` | `2` | 来源、完整性、时点或执行证据不足；不能提供完成快照或正式检查结论 |

unknown 的标准输出为 JSON，包含 `errors` 与 `snapshot: null`。GitHub 原始错误和凭据不回显。

- files 达到 GitHub 3000 条上限，或 `changed_files` 与取得数量不一致时，拒绝可能截断的列表。
- 每页请求 100 条；连续 31 个满页、重复文件路径或审核/评论 ID 会使分页证据不足。
- 不可读资源、限流、超时、部署版本不匹配和 checker 未正常给出兼容结果均返回 unknown。
- 工作流文件是可选部署候选；该模板的模拟验证不启用远端 Actions，也不证明 Required Checks 或服务端审批已经生效。
