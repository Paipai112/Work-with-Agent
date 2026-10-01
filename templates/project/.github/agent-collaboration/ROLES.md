# 角色与授权

所有 Agent 默认是 Member。Member 只能在当前 GitHub 身份和项目规则允许的范围内，
使用日常 Skill 创建任务、首次认领、评论、审查，并实施已认领范围；审查不要求占有
实施 claim。不得把工具名、会话名或编号当作职责身份，也不得自行提升权限、修改
Leader 记录或执行治理配置。Skill 使用要求针对 Agent，人类可按协议参与。

Leader 是显式提升的项目角色，不是默认身份。持久 Leader 只有当
默认分支配置 `managed_paths.authorization` 所选文件（模板默认
[authorization.yml](authorization.yml)）中存在可验证、未撤销的 active
授权记录时，才可作为 Leader 在有效权限内使用 `github-collaboration-setup`。
授权记录中的审批证据、授予时账号权限和冻结的权限上限必须可验证；任何缺失、过期、
冲突或无法核验的情况都按 Member 处理。

配置与授权记录按同一个已确认默认分支 SHA 读取。持久 Leader 授予需用户显式批准，
且目标账号当时至少 Maintain；账号 Admin／Maintain 本身不授予 Agent 角色。首次
Bootstrap 或最后一位 Leader 丢失后的 Recovery 仅由 setup 在用户明确授予的限定
会话与范围内执行，取得明确人类审批、满足实际适用的协议审查及 GitHub 保护门槛，
并在合并后读回，才产生持久授权。已核实保护能力不可用或分支未受保护时，应披露
自动强制及防篡改缺口；身份、授权或实际适用规则未知时，停止相关写入。

有效权限 = 授权上限 ∩ GitHub 账号当前权限 ∩ 项目协议允许范围 ∩ Rulesets / 分支保护

账号从 Maintain 升到 Admin 时，既有 Leader 仍保持 Maintain 上限；账号升级不会自动
扩大授权。账号降权时，有效权限立即下降，只能执行降权后权限允许的操作；低于
Maintain 时不能执行 Leader 治理写入。
每次正式审查、合并和治理操作前重新查询账号权限。

角色不能绕过 GitHub 的实际权限、分支保护、Ruleset 或人工审批。需要扩展权限、修改
治理资源或接管既有资源时，应停止并取得明确批准。
