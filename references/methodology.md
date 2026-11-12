# 审计方法论与已知局限

## 检测维度与实现

| 维度 | 方法 | 阈值/规则 |
|---|---|---|
| 重叠触发 | description 归一化(小写、去标点、保留中英文词;CJK 按字切分)→ SequenceMatcher.ratio + token 集合交集 | ratio ≥ 0.55 且公共词 ≥ 3 → 成对;union-find(按 来源+技能名)成聚类 |
| 常开风格 | description 正则匹配**动作导向**标记(always apply/active、starting any、every task、automatically triggers、use when starting、auto-start 等) | 命中任一 → 常开;自指文本("always-on styles"、"Auto mode")不会误伤 |
| 风格冲突 | 聚类内成员 description 分别命中 minimal 词(minimal/simplest/yagni/lazy)与 maximal 词(comprehensive/thorough/complete) | 同一聚类两种风格并存 → 冲突候选 |

## 扫描范围

- 个人技能:`~/.claude/skills/<name>/SKILL.md`
- 插件技能:`~/.claude/plugins/cache/**/SKILL.md` 递归全量(任意嵌套布局:skills/ 下的分组子目录、插件根、多一层目录等都能覆盖;插件名取路径第二段)
- 去重键:(来源, 技能名);同名多版本只保留先发现的一个。
- **不扫**:marketplace 源码目录(与 cache 重复)、commands/agents(它们有各自命名空间,冲突面不同)。
- **注意**:cache 可能残留已卸载插件的孤儿目录(实战中抓到过 pua-skills 残留)—— 审计发现陌生来源的聚类时,先确认该插件是否已卸载,卸载了就直接删缓存目录。

## 已知局限(诚实声明)

1. **纯文本启发式,无语义**:两个描述用不同措辞说同一件事 → 相似度低会漏;都提到同一触发词但方法不同 → 可能高估。聚类必须人工复核。
2. **常开标记只覆盖英文**:中文 description 的"常开/始终"未入词典(v1),中文技能需人工补充。
3. **hook 驱动的常开技能检测不到**:ponytail 通过 SessionStart hook 常开,其 description 并不含常开标记 —— 报告只覆盖 description 层,还需人工核对各插件的 hooks 配置。
4. **阈值是经验值**:0.55 在本机 86 技能集上标定;技能集变化后需重标定。
5. **"触发域"≠"价值重叠"**:两个技能描述相似但用途互补可能被聚类 —— 治理决定权在人。
6. **行为冲突检测只是代理指标**:真正的冲突发生在正文指令里;v1 用风格关键词近似,漏检不可避免。

## 治理模式速查

| 场景 | 动作 |
|---|---|
| 同域 2 个技能,一个更强 | 禁用弱者,description 保留关键词留给强者 |
| 同域 2 个技能,互补 | 两者 description 各自加上"Not for: X"互斥边界(qa-skills 的写法) |
| 常开技能 ≥2 | 只留一个;其余在 description 加"Use only when..."改成按需 |
| 冲突对无法调和 | 项目级决策,写入 CLAUDE.md 指定优先级 |
