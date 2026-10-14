# 项目协作约定

[config.yml](config.yml)确定版本、受管路径、标签命名空间、集成分支和执行开关。[README 索引](README.md#项目上下文索引)保存事实指针；Issue/PR/事件保存动态证据。

- Agent 日常写操作使用兼容 daily；治理使用获授权 setup；check 仅检查。所有 Agent 默认 Member，账号权限不授予角色。配置及其选定授权从默认分支同一 SHA 读取，候选分支不能授权自己。
- 创建 Issue/首次认领/讨论/审查无需已有实施 claim；实施/Git 写操作需当前有效账号/职责/会话/范围。认领不是锁，未知进程或沉默不是释放证明。
- 任务分支 `agent/<actor_id>/issue-<primary_issue>-<description>` 从核验默认或已登记集成 SHA 派生；叠加交付按同版本 Skill 的固定前置、净 diff 和修订程序。授权源仍为默认分支，内部合并仅是进展。
- 使用配置所选[PR 模板](../PULL_REQUEST_TEMPLATE/agent-change.md)和单一 metadata JSON，无重复键。关闭语句与列表一致，部分交付可不关主 Issue；提交信息关闭关键字不由 checker 核验，合并后读回状态。
- 完整注册入口、嵌套指令入口和重命名两端走治理；缺少 diff 不豁免。只改具体获批块/资源，保留外部字节；dirty 内容处理与 Commit 归属分别确认，冲突/符号链接/未知基线停止相关写入。
- 仅 `git add -- <明确路径>`；禁止 `git add .`、任何 `git add -A`、强推、破坏性重置、自审批绕过及削弱现有保护。
- 正式审查/合并遵守当前 HEAD 的独立协议审查、实际原生审核及保护；写入前刷新权限/来源/任务事实。首次可能触发 Actions 前明确触发/runner/费用批准；启用和 Required Check 分别审批。
- 正式 metadata 仅用默认分支同 SHA 的可信程序，不执行待审代码；最终 PR Action 不适用于内部集成，跳过不是通过。检查不代替真人批准、实时权限或 Skill 加载。未知写入结果先读回；未漂移的包验证记录复用，本地动作不重下全包。
