# skill-audit(中文说明)

审计你安装的全部 Claude Code 技能(个人 + 插件),检测三类风险并给出治理建议:

- **重叠触发**:同一触发域装了多个技能,模型该选谁?
- **常开风格**:多个"每次会话都生效"的技能互相抢戏;
- **风格冲突**:一个要求极简、一个要求完备。

**只读设计:本技能永不自动修改或禁用任何技能**,治理动作由你确认后执行。

## 安装

```bash
cp -r skill-audit ~/.claude/skills/
```

任意 Python 3.7+(纯标准库,零依赖)。

## 用法

```bash
# 全量审计(摘要到 stderr,完整报告写入 ~/.claude/skills/skill-audit-report.md)
python ~/.claude/skills/skill-audit/scripts/audit_skills.py

# 机器可读
python ~/.claude/skills/skill-audit/scripts/audit_skills.py --json

# CI 门禁:检测到指定条件时 exit 1
python ~/.claude/skills/skill-audit/scripts/audit_skills.py --fail-on always_on,clusters

# 使用遥测:哪些 MCP/技能真的在被用、哪些僵尸技能从未触发
python ~/.claude/skills/skill-audit/scripts/audit_usage.py
```

## 局限(诚实声明)

触发词相似度是启发式,聚类需人工复核;"从未调用"只是线索 —— 自动触发的技能不留工具事件。
完整局限见 `references/methodology.md`。

## License

MIT
