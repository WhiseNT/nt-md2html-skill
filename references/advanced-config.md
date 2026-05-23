# nt-md2html 自定义 Widget 构建指南

## 概述

本指南详细介绍如何创建自定义 Widget 组件，遵循 Skill 的设计风格和最佳实践。

---

## 一、自定义 Widget 的两种方式

### 方式一：全局定义（所有文档共享）

编辑 `references/widgets.json`，添加新组件定义：

```json
{
  "my-widget": {
    "description": "我的自定义组件",
    "syntax": "fence",
    "template": "<div class=\"custom\">{{content}}</div>",
    "defaults": {}
  }
}
```

### 方式二：文档级定义（仅当前文档）

在 Markdown 文件的 Front Matter 中定义：

```yaml
---
template: default
widgets:
  my-widget:
    description: 自定义组件描述
    syntax: fence
    template: "<div>{{content}}</div>"
    defaults: {}
---
```

---

## 二、Widget 定义字段说明

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `description` | 否 | string | 组件描述，用于文档说明 |
| `syntax` | 是 | string | `fence`（块级）或 `inline`（行内） |
| `template` | 是 | string | HTML 模板，使用 `{{占位符}}` |
| `defaults` | 否 | object | 属性默认值字典 |

---

## 三、Skill 风格规范

### 3.1 设计原则

1. **简洁优雅**：保持简洁的视觉风格
2. **一致性**：与内置组件风格统一
3. **响应式**：支持不同屏幕尺寸
4. **可访问性**：确保良好的可访问性

### 3.2 颜色规范

| 颜色用途 | CSS 变量 | 默认值 |
|----------|----------|--------|
| 主色调 | `--mhs-primary` | `#667eea` |
| 成功 | `--mhs-success` | `#10b981` |
| 警告 | `--mhs-warning` | `#f59e0b` |
| 错误 | `--mhs-error` | `#ef4444` |
| 边框 | `--mhs-border` | `#e5e7eb` |
| 背景 | `--mhs-bg` | `#ffffff` |
| 文字 | `--mhs-text` | `#1f2937` |

### 3.3 间距规范

| 间距类型 | CSS 变量 | 默认值 |
|----------|----------|--------|
| 小间距 | `--mhs-spacing-sm` | `8px` |
| 中间距 | `--mhs-spacing-md` | `16px` |
| 大间距 | `--mhs-spacing-lg` | `24px` |

### 3.4 圆角规范

| 圆角类型 | CSS 变量 | 默认值 |
|----------|----------|--------|
| 小圆角 | `--mhs-radius-sm` | `6px` |
| 中等圆角 | `--mhs-radius-md` | `8px` |
| 大圆角 | `--mhs-radius-lg` | `12px` |

---

## 四、创建自定义 Widget 步骤

### 步骤 1：确定组件类型

- **围栏型（fence）**：用于块级内容（卡片、面板、容器等）
- **内联型（inline）**：用于行内元素（标签、按钮、图标等）

### 步骤 2：设计属性结构

```json
{
  "callout-box": {
    "description": "自定义提示框",
    "syntax": "fence",
    "template": "<div class=\"mhs-callout-box\"><div>{{title}}</div><div>{{content}}</div></div>",
    "defaults": {
      "title": "提示",
      "variant": "default"
    }
  }
}
```

### 步骤 3：编写模板

使用 `{{占位符}}` 引用属性，`{{content}}` 表示组件内容：

```json
{
  "template": "<div style=\"background: {{bg}}; padding: {{padding}};\">{{content}}</div>"
}
```

### 步骤 4：设置默认值

为可选属性提供合理的默认值：

```json
{
  "defaults": {
    "bg": "#f3f4f6",
    "padding": "16px",
    "border_radius": "8px"
  }
}
```

---

## 五、自定义 Widget 示例

### 示例 1：自定义提示框

```yaml
---
widgets:
  custom-callout:
    description: 自定义提示框
    syntax: fence
    template: >
      <div class="mhs-custom-callout mhs-custom-callout-{{variant}}" style="background: {{bg}}; border-color: {{border}};">
        <div class="mhs-custom-callout-icon">{{icon}}</div>
        <div>
          <h4 class="mhs-custom-callout-title">{{title}}</h4>
          <div class="mhs-custom-callout-body">{{content}}</div>
        </div>
      </div>
    defaults:
      variant: "info"
      title: "提示"
      icon: "💡"
      bg: "#eff6ff"
      border: "#3b82f6"
---
```

**使用方式：**
```markdown
:::custom-callout{title="重要提示", icon="⚠️", variant="warning", bg="#fef3c7", border="#f59e0b"}
这是自定义提示框内容。
:::
```

### 示例 2：自定义标签

```yaml
---
widgets:
  custom-tag:
    description: 自定义彩色标签
    syntax: inline
    template: >
      <span class="mhs-custom-tag" style="background: {{bg}}; color: {{color}}; padding: {{padding}}; border-radius: {{radius}};">
        {{content}}
      </span>
    defaults:
      bg: "#e0e7ff"
      color: "#3730a3"
      padding: "4px 12px"
      radius: "9999px"
---
```

**使用方式：**
```markdown
状态：@custom-tag{bg="#dcfce7", color="#166534"}[已完成]
```

### 示例 3：自定义卡片

```yaml
---
widgets:
  feature-card:
    description: 功能特性卡片
    syntax: fence
    template: >
      <div class="mhs-feature-card" style="background: {{bg}}; border-radius: {{radius}}; padding: {{padding}};">
        <div class="mhs-feature-icon" style="font-size: {{icon_size}};">{{icon}}</div>
        <h3 class="mhs-feature-title">{{title}}</h3>
        <p class="mhs-feature-desc">{{content}}</p>
      </div>
    defaults:
      bg: "#ffffff"
      radius: "12px"
      padding: "24px"
      icon_size: "32px"
      icon: "✨"
---
```

**使用方式：**
```markdown
:::feature-card{icon="🚀", title="高性能", bg="#f8fafc"}
采用最新技术栈，性能卓越。
:::
```

---

## 六、条件渲染

模板支持条件渲染语法：

| 语法 | 说明 |
|------|------|
| `{{#if key}}...{{/if}}` | 当 key 存在且非空时渲染 |
| `{{#unless key}}...{{/unless}}` | 当 key 不存在或为空时渲染 |
| `{{#equals key "value"}}...{{/equals}}` | 当 key 等于指定值时渲染 |
| `{{#each items}}...{{/each}}` | 迭代逗号分隔的列表 |

### 条件渲染示例

```yaml
---
widgets:
  status-card:
    syntax: fence
    template: >
      <div style="padding: 16px; border-radius: 8px; border: 2px solid {{border_color}};">
        {{#if title}}<h3>{{title}}</h3>{{/if}}
        {{#unless hide_content}}<p>{{content}}</p>{{/unless}}
        {{#equals type "warning"}}<div>⚠️ 警告</div>{{/equals}}
        {{#if tags}}
          <div>
            {{#each tags}}<span>{{item}}</span>{{/each}}
          </div>
        {{/if}}
      </div>
    defaults:
      border_color: "#e2e8f0"
      type: ""
---
```

---

## 七、最佳实践

### 7.1 命名规范

- 使用小写字母和连字符：`my-component`
- 避免使用保留字：`card`, `alert`, `btn` 等
- 命名应描述性：`feature-card` 而非 `fc`

### 7.2 模板编写

- 使用语义化 HTML 标签
- 添加合适的 class 用于样式定制
- 支持响应式设计
- 使用 CSS 变量而非硬编码值

### 7.3 属性设计

- 提供合理的默认值
- 属性名使用小写字母
- 避免过多属性（保持简洁）
- 文档化所有属性

### 7.4 性能考虑

- 避免复杂的嵌套结构
- 最小化 DOM 元素数量
- 使用 CSS 动画而非 JavaScript

---

## 八、内置样式类参考

### 布局类

| 类名 | 用途 |
|------|------|
| `mhs-card` | 卡片样式 |
| `mhs-flex` | 弹性布局 |
| `mhs-grid` | 网格布局 |
| `mhs-columns` | 多栏布局 |

### 颜色类

| 类名 | 用途 |
|------|------|
| `mhs-primary` | 主色调 |
| `mhs-success` | 成功状态 |
| `mhs-warning` | 警告状态 |
| `mhs-error` | 错误状态 |

### 间距类

| 类名 | 用途 |
|------|------|
| `mhs-mb-sm` | 底部小间距 |
| `mhs-mb-md` | 底部中间距 |
| `mhs-mb-lg` | 底部大间距 |

---

## 九、完整示例：创建自定义统计卡片

```yaml
---
template: default
widgets:
  stats-card:
    description: 统计数据卡片
    syntax: fence
    template: >
      <div class="mhs-stats-card" style="background: {{bg}}; border-radius: {{radius}}; padding: {{padding}};">
        <div class="mhs-stats-icon" style="background: {{icon_bg}}; color: {{icon_color}}; width: {{icon_size}}; height: {{icon_size}}; border-radius: {{icon_radius}};">{{icon}}</div>
        <div class="mhs-stats-content">
          <div class="mhs-stats-value" style="color: {{value_color}}; font-size: {{value_size}};">{{value}}</div>
          <div class="mhs-stats-label">{{label}}</div>
          {{#if change}}<div class="mhs-stats-change {{change_type}}">{{change}}</div>{{/if}}
        </div>
      </div>
    defaults:
      bg: "#ffffff"
      radius: "12px"
      padding: "20px"
      icon: "📊"
      icon_bg: "#eff6ff"
      icon_color: "#3b82f6"
      icon_size: "48px"
      icon_radius: "12px"
      value: "0"
      value_color: "#1f2937"
      value_size: "28px"
      label: "指标"
      change: ""
      change_type: "up"
---

:::stats-card{icon="👥", value="100万+", label="用户数", change="+12%", change_type="up"}
:::

:::stats-card{icon="💰", value="¥500万", label="销售额", change="-3%", change_type="down", icon_bg="#fef3c7", icon_color="#f59e0b"}
:::
```

---

## 十、调试与验证

### 验证组件定义

```bash
python scripts/render.py --validate-widgets
```

### 调试模式

```bash
python scripts/render.py --file input.md --output output.html --debug
```

---

## 十一、常见问题

### Q1: 自定义组件不显示？

检查：
- 组件名拼写是否正确
- `syntax` 字段是否正确（`fence` 或 `inline`）
- 模板是否有效

### Q2: 属性值不生效？

确保：
- 属性使用双引号：`key="value"`
- 围栏型组件使用正确的闭合标记 `:::`
- 属性名与模板中的占位符一致

### Q3: 如何覆盖内置组件？

在 Front Matter 中定义同名组件即可覆盖内置定义。
