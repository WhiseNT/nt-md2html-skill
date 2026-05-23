# nt-md2html Widget 语法说明

Widget 是可在 Markdown 中简短调用的预定义 HTML 组件，由 `render.py` 在 Markdown 解析之前展开。

***

## 语法概览

| 类型  | 语法                      | 说明   |
| --- | ----------------------- | ---- |
| 围栏型 | `:::组件名{属性="值"} 内容 :::` | 块级组件 |
| 内联型 | `@组件名[内容]{属性="值"}`      | 行内组件 |

***

## 属性规则

1. **格式**: `key="value"`
2. **多个属性**: `key1="value1", key2="value2"`
3. **字符串值**: 必须使用双引号
4. **换行**: 使用 `\n`
   ```markdown
   ```
5. **terminal**
   ```markdown
   terminal
   ```
   **中文**: 支持中文属性值

***

## 完整组件速查表

### 围栏型组件（块级）

| 组件             | 语法示例                                                       | 用途        | 必填属性            |
| -------------- | ---------------------------------------------------------- | --------- | --------------- |
| card           | `:::card{title="标题"} 内容 :::`                               | 信息卡片      | title           |
| alert          | `:::alert{type="warning", title="警告"} 内容 :::`              | 警告提示框     | type, title     |
| callout        | `:::callout{type="info", icon="💡", title="提示"} 内容 :::`    | 强调提示框     | -               |
| details        | `:::details{title="展开"} 内容 :::`                            | 可折叠面板     | title           |
| columns        | `:::columns{cols="3"} 内容 :::`                              | 多栏布局      | cols            |
| grid           | `:::grid{min_width="250", gap="20"} 内容 :::`                | 自适应网格     | -               |
| modal          | `:::modal{id="m1", title="弹窗", trigger="打开"} 内容 :::`       | 模态弹窗      | id              |
| panel          | `:::panel{id="p1", title="面板", position="right"} 内容 :::`   | 滑出面板      | id              |
| hero           | `:::hero{title="标题", subtitle="副标题"} 内容 :::`               | Hero区域    | title, subtitle |
| terminal       | `:::terminal{title="bash"} \`\`\`代码\`\`\` :::`            | 终端窗口      | title           |
| mermaid        | `:::mermaid 图表代码 :::`                                      | Mermaid图表 | -               |
| mindmap        | `:::mindmap{root="中心"} 分支内容 :::`                           | 思维导图      | root            |
| quote          | `:::quote{author="作者"} 内容 :::`                             | 引用块       | author          |
| timeline       | `:::timeline 时间项内容 :::`                                    | 时间轴容器     | -               |
| timeitem       | `:::timeitem{time="2024-01", title="标题"} 内容 :::`           | 时间轴节点     | time, title     |
| kanban         | `:::kanban 看板内容 :::`                                       | 看板容器      | -               |
| kancol         | `:::kancol{title="待办"} 内容 :::`                             | 看板列       | title           |
| ticket         | `:::ticket{id="TASK-1", title="任务", status="todo"} 内容 :::` | 任务卡片      | id, title       |
| features       | `:::features @feature... :::`                              | 功能网格容器    | -               |
| steps          | `:::steps @step... :::`                                    | 步骤容器      | -               |
| stats          | `:::stats @stat... :::`                                    | 统计卡片组     | -               |
| comparison     | `:::comparison @comparison-row... :::`                     | 对比网格      | -               |
| kpi-row        | `:::kpi-row @kpi-card... :::`                              | KPI指标行    | -               |
| status-report  | `:::status-report{title="报告", tag="W48"} :::`              | 状态报告头部    | title           |
| highlights     | `:::highlights{title="亮点"} 内容 :::`                         | 亮点列表      | title           |
| velocity-chart | `:::velocity-chart{title="速度"} @vbar... :::`               | 速度图表      | title           |
| carryover      | `:::carryover{title="遗留"} 内容 :::`                          | 遗留事项容器    | title           |
| carryover-item | `:::carryover-item{status="blocked", title="事项"} 内容 :::`   | 遗留事项      | status, title   |
| milestone-card | `:::milestone-card{time="Q1", title="里程碑"} 内容 :::`         | 里程碑卡片     | time, title     |
| open-question  | `:::open-question{question="问题", decision_with="团队"} :::`  | 开放问题      | question        |
| svg            | `:::svg{caption="图注"} <svg>代码</svg> :::`                   | SVG容器     | -               |
| eval           | `:::eval{title="Eval"} 代码 :::`                             | 代码执行器     | -               |

### 内联型组件（行内）

| 组件               | 语法示例                                                | 用途     | 必填属性                       |
| ---------------- | --------------------------------------------------- | ------ | -------------------------- |
| btn              | `@btn[按钮文本]{variant="primary", href="#"}`           | 按钮     | href                       |
| badge            | `@badge[标签]{variant="success"}`                     | 徽章标签   | -                          |
| kbd              | `@kbd[Ctrl]`                                        | 键盘按键   | -                          |
| progress         | `@progress{percent="75", variant="success"}`        | 进度条    | percent                    |
| tooltip          | `@tooltip[提示]{text="悬浮内容"}`                         | 悬浮提示   | text                       |
| beta             | `@beta[测试中]`                                        | 实验标签   | -                          |
| feature          | `@feature{icon="🚀", title="功能", description="描述"}` | 功能卡片   | icon, title, description   |
| step             | `@step{number="1", title="步骤", description="描述"}`   | 步骤项    | number, title, description |
| stat             | `@stat{value="100", label="标签"}`                    | 统计项    | value, label               |
| comparison-row   | `@comparison-row{pro="优点", con="缺点"}`               | 对比行    | pro, con                   |
| metric-card      | `@metric-card{title="指标", value="100万"}`            | 指标卡片   | title, value               |
| kpi-card         | `@kpi-card{value="95%", label="完成率", delta="+5%"}`  | KPI卡片  | value, label               |
| vbar             | `@vbar{value="10", height="100", day="周一"}`         | 速度图柱子  | value, height, day         |
| numbered-section | `@numbered-section{num="01", title="章节"}`           | 编号章节   | num, title                 |
| top              | `@top[返回顶部]`                                        | 返回顶部   | -                          |
| avatar           | `@avatar[头像]{size="lg"}`                            | 头像     | -                          |
| modal-btn        | `@modal-btn[打开]{target="m1", variant="primary"}`    | 弹窗触发按钮 | target                     |
| panel-btn        | `@panel-btn[打开]{target="p1"}`                       | 面板触发按钮 | target                     |

***

## 核心组件示例

### 1. 信息卡片

```markdown
:::card{title="技术文档"}
这是卡片的正文内容，可以包含 **粗体** 和 *斜体*。

- 列表项 1
- 列表项 2
:::
```

### 2. 功能特性网格

```markdown
:::features
@feature{icon="🚀", title="高性能", description="采用最新技术栈"}
@feature{icon="🎯", title="精准定位", description="智能算法匹配"}
@feature{icon="⚡", title="快速响应", description="毫秒级响应"}
:::
```

### 3. 步骤指示器

```markdown
:::steps
@step{number="1", title="注册账号", description="填写基本信息"}
@step{number="2", title="配置设置", description="个性化配置"}
@step{number="3", title="开始使用", description="享受服务"}
:::
```

### 4. 统计卡片组

```markdown
:::stats
@stat{value="100万+", label="用户"}
@stat{value="50+", label="国家"}
@stat{value="99.9%", label="可用性"}
:::
```

### 5. 对比网格

```markdown
:::comparison
@comparison-row{pro="支持多平台", con="学习曲线较陡"}
@comparison-row{pro="性能卓越", con="资源占用较高"}
@comparison-row{pro="生态完善", con="版本更新频繁"}
:::
```

### 6. Hero 区域

```markdown
:::hero{title="欢迎使用 nt-md2html", subtitle="将 markdown 转换为精美网页"}
@btn[开始使用]{variant="primary", href="#features"}
@btn[了解更多]{variant="secondary", href="#about"}
:::
```

### 7. 终端窗口

Terminal 的代码内容**必须用 ``` 围栏包裹**，围栏 info string 可指定语言（支持 Pygments 语法高亮）：

```markdown
:::terminal{title="javascript"}
```javascript
const arr = [1, 2, 3];
const doubled = arr.map(x => x * 2);
console.log(doubled);
```
:::
```

**语言识别优先级**（从高到低）：
1. ```` ```lang` ```` 围栏的 info string（如 `javascript`、`python`、`bash`）
2. `title` 属性的文件扩展名（如 `title="script.js"` → javascript）
3. `title` 属性的语言名称（如 `title="python"` → python）

**支持的语言**：javascript, typescript, python, bash/shell, json, html, css, sql, java, c/cpp, go, rust, ruby, php, swift, kotlin, scala, r, lua, perl, xml, yaml, markdown, dockerfile, plaintext

```markdown
:::terminal{title="html"}
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"></head>
<body><h1>Hello</h1></body>
</html>
```
:::

:::terminal{title="python"}
```python
def fibonacci(n):
    if n <= 1: return n
    return fibonacci(n-1) + fibonacci(n-2)
print(fibonacci(10))
```
:::

:::terminal{title="bash"}
```bash
#!/bin/bash
echo "Hello, World!"
ls -la *.md
```
:::
```

### 8. 警告提示框

```markdown
:::alert{type="success", title="操作成功"}
数据已成功保存！
:::

:::alert{type="warning", title="警告"}
请确认您的操作。
:::

:::alert{type="error", title="错误"}
操作失败，请重试。
:::
```

### 9. 时间轴

```markdown
:::timeline
:::timeitem{time="2024-01", title="项目启动"}
团队组建完成，开始需求分析。
:::
:::timeitem{time="2024-06", title="Beta发布"}
公开测试版本发布。
:::
:::timeitem{time="2024-12", title="正式上线"}
产品正式运营。
:::
:::
```

### 10. 按钮与徽章

```markdown
@btn[主要按钮]{variant="primary", href="#"}
@btn[次要按钮]{variant="secondary", href="#"}
@btn[幽灵按钮]{variant="ghost", href="#"}

状态：@badge{variant="success"}[完成]
状态：@badge{variant="warning"}[进行中]
```

***

## 自定义组件

### 文档级定义

在 Markdown 文件头部定义，仅对当前文档生效：

```yaml
---
template: default
widgets:
  my-card:
    description: 自定义卡片
    syntax: fence
    template: "<div style='background: {{bg}}; padding: 16px;'>{{content}}</div>"
    defaults:
      bg: "#f3f4f6"
---
```

### 使用自定义组件

```markdown
:::my-card{bg="#dbeafe"}
自定义卡片内容
:::
```

***

## 条件渲染

模板支持条件渲染：

| 语法                                      | 说明             |
| --------------------------------------- | -------------- |
| `{{#if key}}...{{/if}}`                 | 当 key 存在且非空时渲染 |
| `{{#unless key}}...{{/unless}}`         | 当 key 不存在时渲染   |
| `{{#equals key "value"}}...{{/equals}}` | 当 key 等于指定值时渲染 |

***

## 注意事项

1. **闭合标记**: 围栏组件必须以 `:::` 结束
2. **属性引号**: 属性值支持双引号 `"value"` 和单引号 `'value'`
3. **嵌套限制**: Widget 不支持嵌套调用
4. **空白敏感**: `:::` 标记前后建议换行
5. **安全性**: HTML 会经过白名单消毒
6. **Terminal 围栏**: Terminal 组件的代码内容**必须用 ```` ``` ```` 包裹**，不支持直接裸写文本。围栏 info string 可指定语言以启用语法高亮

***

## 扩展资源

- [widgets.json](references/widgets.json) - 完整组件定义
- [advanced-config.md](references/advanced-config.md) - 高级配置指南

