# PR 元数据检查合同

在线入口使用消费项目默认分支同 SHA 检查链；PASS 仅对快照有效，不授权写入/合并，不启用 Actions。

## 运行与结果

需要 Python 3.11+、已登录 `gh`、内容/PR/Issue 读权限；GitHub 请求均为 GET。依赖见可信 `requirements-helpers.txt`（PyYAML/jsonschema），本地不自动安装。

```sh
python3 .github/agent-collaboration/run_pr_metadata_check.py \
  --repository OWNER/REPO --pull-number N --output-dir NEW_DIRECTORY
```

输出 JSON、`metadata.json`、`check-report.json`；省略目录则临时保存、退出清理。持久目录须新建或空，无 symlink/父组件链接/`..`；排他写入保留旧字节。须支持目录描述符、`O_DIRECTORY`、`O_NOFOLLOW`、相对描述符操作，否则 unknown；可省略输出目录，不能降级跟随路径。Windows 原生未验。

| 参数/入口 | 含义 |
| --- | --- |
| `--collect-only` | 仅输出 payload；退出 0 不是正式 PASS |
| `--repository-id`、`--expected-head`、`--expected-trusted-sha` | 目标/漂移约束，仍独立在线核验 |
| `--default-target-only` | 仅默认分支目标适用；本地可检查已登记集成分支 |
| 同目录 `collect_pr_metadata.py` | 相同目标参数，经 launcher 运行可信部署副本 |
| `check_pr_metadata.py INPUT_JSON OUTPUT_DIR` | 离线快照检查，输出 `RESULT=pass/fail/unknown` |
| 离线增加 `--legacy-diagnostic` | 旧输入仅诊断，输出 `LEGACY_RESULT=pass/fail`；移除 snapshot 不可降级取得正式 PASS |

在线 `result: pass/fail/unknown` 分别退出 0/1/2；unknown 含 `errors`、`snapshot: null`，不回显原始 GitHub 错误/凭据。缺资源/依赖、限流、超时、版本不兼容或无合法 checker 结果均为 unknown。

## payload 与来源

| 字段 | 数据 |
| --- | --- |
| `trusted_ref_verified`、`trusted_sha` | 已验证默认分支为 true、完整 40 位 SHA |
| `repository`、`pull` | 仓库 id/full_name/default_branch；PR 原对象含 HEAD/base/作者/正文 |
| `files`、`reviews`、`issues` | 完整分页文件（含 rename）、审核、主/关闭/claim 引用的 Issue |
| `config`、`authorization` | 同 SHA UTF-8 原文；授权路径由 config 选择，不绕开 YAML 原文解析 |
| `claim_comments` | 规范 claim URL→评论；已确认不存在为 null |
| `issue_comments` | 十进制 Issue number 字符串→完整评论列表 |
| `snapshot` | version=2、check_contract=2、source=github-get；collected_at/verified_at、repository_id/default_branch/trusted_sha/pull_number/head_sha/base_ref；trusted_resources 为路径→sha256/bytes |

评论含 `id/url/user_id/login/issue_number/body/updated_at`，核对 ID/URL/Issue/作者，保留正文换行。单条 claim 须与全列表一致；保留 release/handoff/reassign/resume，采集器不裁决授权。

固定目录 `.github/agent-collaboration/` 包含 launcher、collector、checker（上述文件名），`collaboration_event.py`、`collaboration_scope.py`、`collaboration-event.schema.json`、`requirements-helpers.txt`、`config.yml`，另取 config 指定授权，共九项。均须同 SHA 普通 blob、树/Contents 字节及 blob SHA 一致；symlink/gitlink、歧义、截断或单文件超过 262144 字节 → unknown。本地 launcher 字节也须一致，不执行附近替代脚本或 PR 代码。

`COLLECTOR_INPUT_VERSION/INPUT_VERSION=2` 握手输入，`FORMAL_CHECK_VERSION/CHECK_CONTRACT_VERSION=2` 握手判定。新增资源须同步固定清单/setup 映射/握手，不动态加载。Actions 校验同 SHA requirements 后建临时 venv/pip、调用同一入口；仅模拟验证，启用另批。

## 固定交付与事件

PR 唯一 metadata 块使用 `schema_version: 2`；完整结构见[规范模板](../PULL_REQUEST_TEMPLATE/agent-change.md)。必填 delivery：development_base_sha（有效 claim 当前 base_head）、net_diff_base_sha、predecessors（按序含 pull_number/head_sha）、merge_order（前置编号后接本 PR）。SHA 完整；无前置仍须空 predecessors 和本 PR 真实编号（先建 Draft 再补）。开发基线不是授权 trusted_sha。

collector 提供 `predecessor_pulls`（声明顺序）、`predecessor_files`（number 字符串→全量文件）、`development_compare`、`net_diff`、`predecessor_compares`。比较均含 base_sha/head_sha/merge_base_sha/status/commits/files/complete；commits 为完整分页 SHA。相邻前置比较数量为 max(前置数−1,0)，验证实际祖先顺序，不只信 merge_order。

- 有未合并前置：仅 Draft，两基线为最后前置固定 HEAD。总 diff 须能由真实前置文件与当前净增量解释；净增量过当前 claim scope。继承 added、净 modified 不强求同状态。
- 前置全合并：净基线为当前 PR target SHA；API/net 路径、状态、rename 两端元组一致并过 scope。关闭未合并/固定 HEAD 漂移拒绝；无法解释为 unknown。squash/rebase 不默认收敛，重新核验基线/净 diff/审核，不自动 rebase/force。
- 基线修订追加 claim 并链接前驱；revision 的 schema_version=1、kind=baseline，原始根 original_event_id/github_comment_id/github_comment_url/old_body_sha256、reason、from_base_head/to_base_head 必填。from 为前驱有效基线，to 为新值；身份/session/branch/scope 不变。correction 不得改基线；范围变化另行认领/预检，不追认旧写入。
- 重分配核验可信 Leader 委派结构、精确目标和继任 claim；旧进程 unknown 必须独立分支。没有 native APPROVED 不自动失败；已有证据须对应当前 HEAD 且晚于相关合并/基线修订。

## 完整性与未核验事项

每页 100 条；31 个满页、重复路径/审核/评论 ID、文件数与 changed_files 不符或达到 3000 上限 → unknown。[Compare API](https://docs.github.com/en/rest/commits/commits#compare-two-commits) 文件仅第一页、最多 300；达到 300 即 unknown。比较提交完整分页、末项固定 HEAD。结束前二次 GET 仓库/default SHA/PR/Issue/评论/审核/前置/比较；任何漂移重采集，合并前仍须再次刷新。

离线来源标记/complete 可被改写，不是签名；实时来源须在线核验。unverified：真人批准、实时权限、原生保护/Required Reviews、Skill 加载、协议当前 HEAD 审核、未列 Issue 冲突、历史逐次写入授权、旧进程终止。只采相关 Issue，拒绝已知冲突，不证明全仓独占。共享账号职责审核不等于原生独立账号审批；最终按项目规则核验。
