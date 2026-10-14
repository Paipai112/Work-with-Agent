# 角色与授权兼容入口

所有 Agent 默认 Member。当前职责/账号与委任记录由已确认默认分支[配置](config.yml)选择的[授权](authorization.yml)核实；两者必须来自同一 SHA。完整计算与操作流程由已验证 Skill 的 session-core 和授权参考提供，本页不是 grant。

有效权限 = 授权上限 ∩ GitHub 账号当前权限 ∩ 项目协议允许范围 ∩ Rulesets / 分支保护

账号从 Maintain 升到 Admin 时，既有 Leader 仍保持 Maintain 上限。账号降权时，有效权限立即下降；低于 Maintain 失去 Leader 权限。具体职责范围和每次动作的批准仍须满足；正式审查、合并、治理前刷新证据。

已有项目若在旧 ROLES.md 中保存自定义职责或规则，setup 先盘点并展示明确迁移差异，保留原文与历史，获得批准后才迁移；不能因本指针较短就删除或覆盖旧文件。
