# 参与贡献

本仓库维护 Baton：一套基于 GitHub 的多 Agent 协作体系（协议、两个 Skill 与项目模板）。仓库文档以中文为主，技能、脚本与模板内文为英文。

## 提交改动

- 保持 `schemas/`、`templates/`、`shared/` 为规范源。修改这些目录后运行同步：

  ```sh
  python3 scripts/sync_skill_resources.py --skill github-collaboration-setup --accept-reviewed-diff
  python3 scripts/sync_skill_resources.py --skill github-collaboration --accept-reviewed-diff
  ```

- 提交前在本地执行：

  ```sh
  python3 scripts/verify_skill_packages.py
  ```

  以及 [验证说明](docs/VALIDATION.md) 中的离线回归子集；这两项也是 CI 的检查内容，先本地通过再提交。

- 行为变化（协议语义、检查器判定、技能规则）需同步更新测试与 [发行说明](docs/RELEASE_NOTES.md) 的对应段落。
- 版本发行由维护者按固定标签发布；提交中不要自行创建标签或 Release。

## 报告问题

功能问题与提案使用 GitHub Issues；安全问题请按 [SECURITY.md](SECURITY.md) 的渠道提交。
