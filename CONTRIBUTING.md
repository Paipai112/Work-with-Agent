# 参与贡献

本仓库维护 Work-with-Agent：GitHub 多 Agent 协作协议、三个独立 Skill 与项目模板。仓库文档以中文为主，Skill 和脚本内文以英文为主。

## 一、提交改动

- 保持 `schemas/`、`templates/`、`shared/` 和 daily 包中的六类事件模板为规范源。三个包的复制关系由 `scripts/skill_resource_profiles.py` 显式列出；不手工修改复制件。先检查本地差异，再同步已审阅的资源：

  ```sh
  python3 scripts/sync_skill_resources.py --skill github-collaboration-setup --accept-reviewed-diff
  python3 scripts/sync_skill_resources.py --skill github-collaboration --accept-reviewed-diff
  python3 scripts/sync_skill_resources.py --skill github-collaboration-check --accept-reviewed-diff
  ```

- 提交前在本地执行：

  ```sh
  python3 scripts/verify_skill_packages.py
  ```

  以及 [验证说明](docs/VALIDATION.md) 中的离线回归子集；这两项也是 CI 的检查内容，先本地通过再提交。

- 行为变化（协议语义、检查器判定、技能规则）需同步更新测试与 [发行说明](docs/RELEASE_NOTES.md) 的对应段落。
- 新行为先写可复现的失败用例，再做最小实现；配置候选和发行包使用真实产物自解析，不以手工 fixture 或字面关键词断言代替行为证据。
- 用户改动、未知结果、缺失证据均保留原状态并报告；测试通过不授予提交、推送、合并或远端设置权限。
- 版本发行由维护者按固定标签发布；提交中不要自行创建标签或 Release。

## 二、标识符纪律

以下机器标识符按原名保持稳定（含 `github-agent-collaboration` 字样），改动会破坏已安装的消费项目，不要为与仓库名一致而修改：

- 技能目录：`github-collaboration-setup`、`github-collaboration`、`github-collaboration-check`
- 受管区块标记：`github-agent-collaboration`（亦是 `managed_block.py` 等脚本的默认参数值）
- schema `$id` 前缀：`https://schemas.github-agent-collaboration.dev/v1/`（标识符，不是可访问站点）
- 治理文件路径：`.github/agent-collaboration/`

## 三、报告问题

功能问题与提案使用 GitHub Issues；安全问题请按 [SECURITY.md](SECURITY.md) 的渠道提交。
