---
name: nt-md2html
version: "2.1"
description: Markdown到HTML智能转换引擎，支持富文本组件、自动目录生成、多主题模板，专为Agent协作设计。
---

# nt-md2html Skill

## 扩展资源

| 文档 | 用途 | 加载时机 |
|------|------|----------|
| [widget-syntax.md](references/widget-syntax.md) | 完整组件列表 + 语法 | 生成内容时 |
| [widgets.json](references/widgets.json) | 组件定义 | 组件使用 |
| [advanced-config.md](references/advanced-config.md) | 自定义组件 + 高级配置 | 创建自定义组件时 |
| [eval.json](references/eval.json) | 执行评估标准 | 优化执行质量 |

---

## 工作流程规范

### 标准渲染流程（推荐）

```
1. 评估内容
   └─ 分析 Markdown 内容 → 识别适合的组件类型
2. 组件化
   └─ 将纯文本转换为 Widget 语法
3. 检查组件支持
   └─ 所需组件存在？
       ├─ YES → 继续
       └─ NO → 创建自定义组件或使用纯 Markdown
4. 渲染
   └─ python scripts/render.py --file output.md --output output.html
```

### 执行命令

```bash
# 基本渲染
python scripts/render.py --file input.md --output output.html

# 指定主题
python scripts/render.py --file input.md --output output.html --template dark

# 验证组件定义
python scripts/render.py --validate-widgets

# 调试模式
python scripts/render.py --file input.md --output output.html --debug

# stdin模式
echo "# 标题" | python scripts/render.py > output.html
```

### 输出规范

**必须输出两个文件：**
- `{name}.md` - 源文件（AI可读，可编辑）
- `{name}.html` - 最终文件（人类可读）

---

## Markdown 编写规范

### 通用 Markdown 规则

1. **标题层级**：`#` 后必须有空格，层级应从 `#`（h1）开始逐级递增，不可跳级（如 h1 → h3）
2. **列表格式**：无序列表用 `-`，有序列表用 `1.`，列表项之间用空行分隔
3. **代码块**：使用 ` ``` ` 包裹代码块并指定语言（如 ` ```python `），行内代码使用单反引号
4. **表格**：表头与表体之间用 `|---|---|` 分隔，列对齐用 `:---`（左）、`:---:`（居中）、`---:`（右）
5. **链接与图片**：`[文本](url)` 和 `![替代文本](url)` 格式，URL 无需额外引号
6. **粗体/斜体**：`**粗体**`（偶数个 `**`）、`*斜体*`（偶数个 `*`），不可混用
7. **水平线**：使用 `---`，前后需空行，避免与标题语法冲突

### Widget 组件编写规则

1. **围栏组件**：以 `:::` 开头和闭合，嵌套时外层用 `:::`、内层用 `::::`（递增冒号数量）
2. **内联组件**：格式为 `@组件名[内容]{属性="值"}`，属性值必须使用双引号
3. **属性格式**：多个属性用逗号分隔，如 `key1="value1", key2="value2"`
4. **组件名**：使用小写字母和连字符，如 `status-report`、`milestone-card`
5. **内容换行**：`:::` 标记前后建议各空一行，确保解析正确
6. **自定义组件**：在 Front Matter 的 `widgets:` 中定义，或加载 [advanced-config.md](references/advanced-config.md)

### 避坑指南

| 常见错误 | 正确写法 | 说明 |
|----------|----------|------|
| `#标题`（无空格） | `# 标题` | `#` 后必须加空格 |
| `**文字`（不闭合） | `**文字**` | 粗体标记必须成对出现 |
| `:::card` 后不闭合 | `:::card ... :::` | 围栏组件必须闭合 |
| 嵌套冒号数相同 | 外层 `:::`，内层 `::::` | 嵌套时冒号数递增 |
| `key='value'` 单引号 | `key="value"` | 属性值必须用双引号 |
| `{}` 内无空格 | `{key="val"}` | 属性紧贴大括号，无多余空格 |
| 标准 mermaid 代码块 | `:::mermaid` 语法 | 使用 Widget 语法渲染 |
| 组件名大小写混用 | `status-report` 全小写 | 组件名统一用小写+连字符 |

---

## 场景分类

## 场景分类

### 场景A：有现成.md文件

```
1. 分析现有内容结构
2. 评估是否需要组件化
3. 如需组件化，修改.md文件添加Widget语法
4. 执行渲染命令
```

### 场景B：从零创建内容

```
1. 规划内容结构
2. 加载组件规格（references/widget-syntax.md）
3. 使用Widget语法编写Markdown
4. 执行渲染命令
```

---

## Subagent 委派协议

### 何时使用 Subagent

| 场景 | 推荐 |
|------|------|
| 已有 Markdown 文件需要渲染 | ✅ |
| 内容复杂度中等或以上 | ✅ |
| 需要并行处理提升效率 | ✅ |
| 简单的单次转换 | ❌ |
| 需要实时交互反馈 | ❌ |

### 委派消息格式

```
[NTMD2HTML_DELEGATE]
task: render
input: {文件路径或内容}
theme: {default|dark}
output: {输出路径}
load_full_specs: true
```

### Subagent 必须执行的操作

1. 读取 `widget-syntax.md`（完整组件列表）
2. 读取 `widgets.json`（组件定义）
3. 从60个组件中选择最优方案
4. 必要时创建自定义组件

---

## 组件选择指南

| 内容类型 | 推荐组件 |
|----------|----------|
| 信息容器 | `card` |
| 操作引导 | `btn` |
| 数据展示 | `progress` / `stats` / `metric-card` |
| 对比布局 | `columns` / `comparison` |
| 导航跳转 | `toc` |
| 步骤流程 | `steps` / `step` |
| 特色展示 | `features` / `feature` |
| 时间线 | `timeline` / `timeitem` |
| 看板 | `kanban` / `kancol` / `ticket` |
| 交互弹窗 | `modal` / `panel` |
| 代码展示 | `terminal` |
| 引用块 | `quote` |
| 提示强调 | `callout` / `alert` |
| 标签徽章 | `badge` / `beta` |
| 悬浮提示 | `tooltip` |
| 键盘按键 | `kbd` |

---

## 版本更新

### v2.1
- 🐛 修复模板字符串内嵌反引号解析错误
- 🐛 修复CSS文件编码乱码问题
- 📝 规范化工作流程文档
- ✨ 添加eval.json评估配置

### v2.0
- ✨ 组件化工作流（评估→组件化→检查→渲染）
- ✨ 自定义组件询问机制
- ✨ 分层信息披露优化
- ✨ Subagent 完整委派协议

### v1.x
- 基础组件系统
- Markdown 到 HTML 转换
- 主题支持
