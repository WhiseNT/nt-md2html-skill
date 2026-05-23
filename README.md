# nt-md2html

Markdown 到 HTML 智能转换引擎，支持富文本组件（Widget）、自动目录生成、多主题模板，专为 Agent 协作设计。

## 特性

- **60+ 内置组件** — 卡片、按钮、时间线、看板、终端窗口等，覆盖常见内容场景
- **Widget 语法** — 围栏型（`:::`）和内联型（`@`）两种组件形式，直观易用
- **自定义组件** — 通过 Front Matter 或全局 JSON 定义新组件，支持条件渲染和迭代
- **多主题** — 内置 `default` 和 `dark` 两套主题，可扩展
- **代码高亮** — 基于 Pygments，支持 20+ 编程语言语法高亮
- **安全消毒** — 基于 nh3 的 HTML 白名单过滤，防止 XSS
- **Subagent 协作** — 完整的委派协议，支持任务分发与结果回传
- **智能编码** — 自动检测文件编码（UTF-8/GBK/Big5 等），兼容 Windows 环境

## 快速开始

### 安装依赖

```bash
pip install -r scripts/requirements.txt
```

依赖项：

- `markdown-it-py>=3.0.0` — Markdown 解析
- `nh3>=0.2.0` — HTML 安全消毒
- `PyYAML>=6.0` — Front Matter 解析

可选依赖（代码高亮）：

- `pygments` — 语法高亮

### 基本用法

```bash
# 渲染 Markdown 文件
python scripts/render.py --file input.md --output output.html

# 指定主题
python scripts/render.py --file input.md --output output.html --template dark

# 从命令行传入 Markdown 文本
python scripts/render.py --markdown "# Hello World" --output output.html

# 从标准输入读取
echo "# 标题" | python scripts/render.py > output.html
```

## Widget 语法

### 围栏型组件（块级）

```markdown
:::card{title="项目概览"}
这是卡片内容，支持 **Markdown** 语法。
:::
```

### 内联型组件（行内）

```markdown
@btn[开始使用]{variant="primary", href="#"}
@badge[已完成]{variant="success"}
```

### 嵌套组件

外层使用 `:::`，内层递增冒号数：

```markdown
:::timeline
::::timeitem{time="2024-Q1", title="阶段一"}
内容
::::
::::timeitem{time="2024-Q2", title="阶段二"}
内容
::::
:::
```

### 常用组件速查

| 内容类型 | 组件 | 类型 |
|----------|------|------|
| 信息卡片 | `card` | fence |
| 按钮 | `btn` | inline |
| 进度条 | `progress` | inline |
| 统计数据 | `stats` + `stat` | fence+inline |
| 功能特性 | `features` + `feature` | fence+inline |
| 步骤流程 | `steps` + `step` | fence+inline |
| 时间线 | `timeline` + `timeitem` | fence+fence |
| 终端代码 | `terminal` | fence |
| 警告提示 | `alert` / `callout` | fence |
| 对比表格 | `comparison` + `comparison-row` | fence+inline |
| Hero 区域 | `hero` | fence |
| 模态弹窗 | `modal` | fence |
| 标签徽章 | `badge` | inline |
| 键盘按键 | `kbd` | inline |

完整组件列表和语法详见 [references/widget-syntax.md](references/widget-syntax.md)。

## 自定义组件

在 Markdown 文件的 Front Matter 中定义自定义组件：

```yaml
---
template: default
widgets:
  my-card:
    description: 自定义卡片
    syntax: fence
    template: '<div style="background: {{bg}}; padding: 16px;">{{content}}</div>'
    defaults:
      bg: "#f3f4f6"
---
```

使用：

```markdown
:::my-card{bg="#dbeafe"}
自定义卡片内容
:::
```

模板支持条件渲染：`{{#if key}}...{{/if}}`、`{{#unless key}}...{{/unless}}`、`{{#equals key "value"}}...{{/equals}}`、`{{#each items}}...{{/each}}`。

详见 [references/advanced-config.md](references/advanced-config.md)。

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--file <path>` | 输入 Markdown 文件路径 |
| `--markdown <text>` | 直接传入 Markdown 文本 |
| `--output <path>` | 输出 HTML 文件路径 |
| `--template <name>` | 主题名称（`default` / `dark`） |
| `--stream` | 启用流式输入模式 |
| `--widget-defs <path>` | 自定义 Widget 定义 JSON 路径 |
| `--validate-widgets` | 验证 Widget 定义语法 |
| `--debug` | 调试模式 |
| `--allow-eval` | 启用 eval 组件（默认禁用） |
| `--delegate <msg>` | 执行 Subagent 委派任务 |
| `--suggest-workflow` | 获取工作流建议 |
| `--check-subagent` | 检测 Subagent 可用性 |
| `--validate-output <files>` | 验证输出文件 |

## 工作流程

```
1. 评估内容 → 分析 Markdown，识别适合的组件类型
2. 组件化   → 将纯文本转换为 Widget 语法
3. 检查支持 → 所需组件存在？YES → 继续 / NO → 创建自定义组件
4. 渲染     → python scripts/render.py --file output.md --output output.html
```

**输出规范**：每次渲染生成两个文件 — `.md` 源文件（AI 可读，可编辑）和 `.html` 最终文件（人类可读）。

## 项目结构

```
nt-md2html-skill/
├── SKILL.md                    # Skill 定义文件
├── scripts/
│   ├── render.py               # 核心渲染器
│   ├── workflow_helper.py      # 工作流辅助工具
│   └── requirements.txt        # Python 依赖
├── references/
│   ├── widget-syntax.md        # 完整组件语法说明
│   ├── widgets.json            # 组件定义
│   ├── advanced-config.md      # 自定义组件构建指南
│   ├── eval.json               # 执行评估标准
│   └── templates/
│       ├── default.html        # 默认主题模板
│       └── dark.html           # 暗色主题模板
├── assets/
│   └── themes/
│       ├── default.css         # 默认主题样式
│       └── dark.css            # 暗色主题样式
└── LICENSE                     # MIT License
```

## 渲染管线

```
Front Matter 解析 → Widget 展开 → Markdown 解析 → 安全消毒 → 模板注入 → 输出
```

1. **Front Matter 解析** — 提取模板、自定义组件等元数据
2. **Widget 展开** — 递归展开围栏型和内联型组件，支持深层嵌套
3. **Markdown 解析** — 基于 markdown-it-py 的 GFM 风格解析，自动生成标题锚点和目录
4. **安全消毒** — nh3 白名单过滤，保留安全 HTML 标签和属性
5. **模板注入** — 将内容注入主题模板，替换 `{{content}}` 和 `{{css}}`
6. **输出** — 生成完整的 HTML 文件

## 许可证

[MIT](LICENSE) &copy; WhiseNT
