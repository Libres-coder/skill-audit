---
name: skill-audit
description: "Audit all installed Claude Code skills (personal + plugin) for overlapping triggers, competing always-on styles, and possible conflicting mandates, then produce a remediation plan. Use when the wrong skill fires, when the agent's style feels inconsistent (minimal vs comprehensive), after any skill/plugin install or removal, when many skills were installed and need governance, or when the user asks to audit/check the skills collection (技能审计/冲突/重叠/查重/常开/打架/风格飘忽/治理). Read-only; makes no changes."
---

# Skill Audit(技能治理审计)

扫描全部已装技能,输出重叠触发、常开风格、风格冲突三类风险与治理建议。
**只读 —— 本技能从不修改或禁用任何技能,治理动作由你确认后执行。**

## 何时用

- 装了一堆技能后,AI 触发行为飘忽(该触发的不触发、风格忽简忽繁);
- 用户说"审计技能 / 查重叠 / 技能太多会不会打架";
- 每次增删技能/插件之后(建议养成习惯)。

## 工作流

### 1. 跑审计

```bash
uv run --no-project python ~/.claude/skills/skill-audit/scripts/audit_skills.py
# 无 uv 时:python ~/.claude/skills/skill-audit/scripts/audit_skills.py(纯标准库)
```

stdout 给 ASCII 摘要;完整报告写入 `~/.claude/skills/skill-audit-report.md`(UTF-8)。
参数:`--threshold`(默认 0.55,越低越敏感)、`--json`(stdout 仅输出 JSON,不写报告文件)、`--output <路径>`、`--skills-dir/--plugins-dir`。

### 2. 读报告,按三类风险处理

- **Overlap clusters(重叠聚类)**:同一触发域多个技能 —— 每个域只留一个,其余禁用或删除(同一插件内部的有意变体对,如 grill-me/grill-with-docs,人工判定后通常保留);
- **Always-on(常开风格)**:数量应 ≤1。以本次审计实际列出的常开技能为准做取舍;**hook 驱动的常开(如 ponytail)description 检测不到,需人工核对各插件的 hooks 配置**;
- **Conflict candidates(风格冲突)**:minimal 与 comprehensive 并存 —— 由用户拍板哪个风格适用于当前项目,不替用户决定。

### 2.5 使用遥测(技能/插件是否真的在被用)

```bash
uv run --no-project python ~/.claude/skills/skill-audit/scripts/audit_usage.py
```

扫描全部会话转录,报告:**MCP 服务器实际调用次数/会话数/最近使用**、显式 Skill 调用、斜杠命令、**从未被调用的个人技能清单**。
报告写入 `~/.claude/skills/skill-usage-report.md`;`--json` 机器可读。
**诚实局限**:自动触发的技能不会产生工具事件,所以"从未调用"只是线索而非证据;MCP 统计只含会话内工具调用,不含连接本身的开销。用它与 `claude mcp list`、插件安装时间交叉判断"沉默负债"。

### 3. 执行治理 + 复测

1. 禁用:`claude plugin disable <name>@<marketplace>`;个人技能删除目录(先备份);
2. 改 description 时遵循 skill-creator 插件的触发词规范(本机已装);
3. **治理后必复跑审计**,确认聚类/常开数量下降 —— 用证据说话。

## 硬规则

- 本技能只报告,不自动执行禁用/删除 —— 治理动作必须由用户确认;
- 相似度阈值是启发式,聚类结果必须人工复核后再动手(参考 references/methodology.md 的已知局限);
- 报告文件会覆盖上次结果,重要结论请抄入对话或 PROGRESS。
