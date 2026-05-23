# nt-md2html Agent 使用指南

## 扩展资源

| 文档 | 用途 | 加载时机 |
|------|------|----------|
| [widget-syntax.md](references/widget-syntax.md) | 完整组件列表 + 语法 | 生成内容时 |
| [widgets.json](references/widgets.json) | 组件定义 | 组件使用 |
| [advanced-config.md](references/advanced-config.md) | 自定义组件 + 高级配置 | 创建自定义组件时 |
| [eval.json](references/eval.json) | 执行评估标准 | 优化执行质量 |

---

## 快速开始

### 核心工作流程

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

### 输出规范

**必须输出两个文件：**
- `{name}.md` - 源文件（AI可读，可编辑）
- `{name}.html` - 最终文件（人类可读）

---

## 场景处理指南

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

## 组件语法规范

### 两种组件类型

**围栏型组件（Fence Widgets）** - 用于块级内容

```markdown
:::组件名{属性="值"}
组件内容（支持 Markdown）
:::
```

**内联型组件（Inline Widgets）** - 用于行内元素

```markdown
@组件名[内容]{属性="值"}
```

### 属性规则

1. 格式：`key="value"`
2. 多个属性用逗号分隔：`key1="value1", key2="value2"`
3. 属性值必须使用双引号
4. 属性值中的换行使用 `\n`
5. 支持中文属性值

---

## 常用组件速查表

| 内容类型 | 推荐组件 | 组件类型 |
|----------|----------|----------|
| 信息卡片 | `card` | fence |
| 按钮链接 | `btn` | inline |
| 进度展示 | `progress` | inline |
| 统计数据 | `stats` + `stat` | fence+inline |
| 功能特性 | `features` + `feature` | fence+inline |
| 步骤流程 | `steps` + `step` | fence+inline |
| 时间线 | `timeline` + `timeitem` | fence+fence |
| 对比表格 | `comparison` + `comparison-row` | fence+inline |
| 终端代码 | `terminal` | fence |
| 警告提示 | `alert` / `callout` | fence |
| 标签徽章 | `badge` | inline |
| 悬浮提示 | `tooltip` | inline |
| Hero区域 | `hero` | fence |
| 模态弹窗 | `modal` | fence |

---

## 核心组件示例

### 功能特性网格

```markdown
:::features
@feature{icon="🚀", title="高性能", description="采用最新技术栈，性能卓越。"}
@feature{icon="🎯", title="精准定位", description="智能算法，精准匹配。"}
@feature{icon="⚡", title="快速响应", description="毫秒级响应，流畅体验。"}
:::
```

### 步骤指示器

```markdown
:::steps
@step{number="1", title="第一步", description="描述内容"}
@step{number="2", title="第二步", description="描述内容"}
@step{number="3", title="第三步", description="描述内容"}
:::
```

### 统计卡片组

```markdown
:::stats
@stat{value="100万+", label="用户"}
@stat{value="50+", label="国家"}
@stat{value="99.9%", label="可用性"}
:::
```

### 对比网格

```markdown
:::comparison
@comparison-row{pro="优点 A", con="缺点 A"}
@comparison-row{pro="优点 B", con="缺点 B"}
@comparison-row{pro="优点 C", con="缺点 C"}
:::
```

### Hero 区域

```markdown
:::hero{title="欢迎使用", subtitle="将 markdown 转换为精美网页"}
@btn[开始使用]{variant="primary", href="#"}
@btn[了解更多]{variant="secondary", href="#"}
:::
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
3. 从组件中选择最优方案
4. 必要时创建自定义组件

---

## 执行命令

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

---

## AI 使用规范

### 必须遵守的规则

1. **组件类型判断**：围栏型用于大块内容，内联型用于行内元素
2. **语法正确性**：围栏组件必须以 `:::` 闭合
3. **属性完整性**：提供组件所需的属性
4. **编码规范**：使用 UTF-8 编码

### 常见错误避免

- ❌ 不要省略围栏组件的闭合标记 `:::`
- ❌ 不要使用单引号包裹属性值
- ❌ 不要在属性值中使用未转义的特殊字符

---

## Markdown 编写规范（完整版）

### 一、基础 Markdown 语法规则

| 语法元素 | 正确写法 | 常见错误 | 检查要点 |
|----------|----------|----------|----------|
| 标题 | `# 标题`（`#` 后须有空格） | `#标题`（无空格） | `#` 后空格、层级不跳级 |
| 粗体 | `**文字**` | `**文字`（不闭合） | `**` 必须成对出现 |
| 斜体 | `*文字*` | `文字*`（不闭合） | `*` 必须成对出现 |
| 无序列表 | `- 项目` | `-项目`（无空格） | `-` 后须有空格 |
| 有序列表 | `1. 项目` | `1.项目`（无空格） | `数字.` 后须有空格 |
| 代码块 | ` ```python ... ``` ` | ` ``` `无语言标识 | 始终指定代码语言 |
| 行内代码 | `` `代码` `` | 无反引号包裹 | 单反引号包裹 |
| 链接 | `[文本](url)` | `[文本](url "title")` | URL 无需引号包裹 |
| 图片 | `![alt](url)` | `![]()` 缺少 alt | 始终提供替代文本 |
| 表格 | `\| 列1 \| 列2 \|` | 缺少分隔行 | 表头后必须有 `|---|---|` |
| 水平线 | `---`（前后空行） | 与标题混淆 | `---` 前后必须空行 |
| 引用块 | `> 内容` | `>内容`（无空格） | `>` 后须有空格 |

### 二、Widget 组件编写规则

#### 2.1 围栏组件（Fence Widgets）

```markdown
:::组件名{属性="值"}
组件内容（支持 Markdown 语法）
:::
```

**关键规则：**
1. **必须闭合**：每个 `:::` 开头的组件必须用 `:::` 结束，不可遗漏
2. **嵌套规则**：嵌套时外层用 `:::`，内层用 `::::`（冒号数递增 1）
3. **属性规范**：属性写在开始标记行的大括号 `{}` 中
4. **空行分隔**：`:::` 标记前后建议各空一行，避免解析歧义
5. **首行保持**：组件内容的第一行紧跟在 `:::` 行之后，不空行

**嵌套示例：**
```markdown
:::timeline

::::timeitem{time="2024-Q1", title="阶段一"}
内容支持 **Markdown** 语法
::::

::::timeitem{time="2024-Q2", title="阶段二"}
内容支持 *斜体* 和 `代码`
::::

:::
```

#### 2.2 内联组件（Inline Widgets）

```markdown
@组件名[显示内容]{属性="值"}
```

**关键规则：**
1. **属性值必须是双引号**：`key="value"`，不可使用单引号
2. **多个属性用逗号分隔**：`key1="val1", key2="val2"`
3. **属性值中的特殊字符**：换行用 `\n`，双引号用 `\"` 转义
4. **空白处理**：`@` 前可接普通文本，`@` 后紧跟组件名，无空格

#### 2.3 属性格式细则

```markdown
✅ 正确示例：
:::card{title="项目概览", width="full"}
@btn[查看详情]{variant="primary", href="#details"}

❌ 错误示例：
:::card{title='项目概览'}           ← 单引号，错误
:::card{title=项目概览}             ← 无双引号，错误
@btn[查看详情]{variant=primary}     ← 属性值无双引号，错误
```

### 三、组件命名规范

- **格式**：全小写字母 + 连字符 `-`
- **示例**：`status-report`、`milestone-card`、`open-question`、`carryover-item`
- **禁止**：驼峰式（`StatusReport`）、下划线（`status_report`）、空格
- **自定义组件**：同样遵循此命名规范，在 Front Matter 中定义

### 四、常见错误自查表

在编写 Markdown 时，逐一核对以下检查点：

| 编号 | 检查项 | 说明 |
|------|--------|------|
| 1 | 围栏组件是否闭合？ | 每个 `:::组件名` 必须有对应的 `:::` |
| 2 | 嵌套冒号数是否正确？ | 外层 `:::`，内层 `::::`（+1） |
| 3 | 是否使用未定义组件？ | 组件名拼写是否正确？在 widgets.json 中？ |
| 4 | Mermaid 语法是否正确？ | 应使用 `:::mermaid` 而非 ` ```mermaid ` |
| 5 | 粗体/斜体是否成对？ | `**` 和 `*` 必须为偶数个 |
| 6 | 属性值是否为双引号？ | `key="value"` 而非 `key='value'` |
| 7 | 标题 `#` 后是否有空格？ | `# 标题` 而非 `#标题` |
| 8 | 代码块是否指定语言？ | ` ```python ` 而非 ` ``` ` |
| 9 | 表格是否有分隔行？ | 表头后须有 `|---|---|` 行 |
| 10 | 列表标记后是否有空格？ | `- 项目` 而非 `-项目` |
| 11 | 组件名是否全小写？ | `status-report` 而非 `Status-Report` |
| 12 | 嵌套组件内容格式？ | 内层组件内容是否被正确包裹？ |
| 13 | Front Matter YAML 格式？ | `key: value` 缩进是否正确？ |
| 14 | 属性值含特殊字符？ | `"` 需转义为 `\"`，换行为 `\n` |

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
