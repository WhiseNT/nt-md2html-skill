#!/usr/bin/env python3
"""
nt-md2html — Markdown 到 HTML 的通用渲染器。

管道：Front Matter 解析 → Widget 展开 → Markdown 解析 → 安全消毒 → 模板注入 → 输出。

用法：
  python render.py --markdown "# Hello" --template dark
  python render.py --stream < input.md
  echo "# Hi" | python render.py
"""

from __future__ import annotations

import argparse
import locale

_DEBUG_MODE = False
_EVAL_ALLOWED = False
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

if sys.version_info[0] >= 3 and sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ENCODING_FALLBACKS = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'big5', 'cp1252']
MAX_INPUT_SIZE = 10 * 1024 * 1024


def _detect_and_read_file(filepath: Path) -> str:
    """智能检测文件编码并读取内容"""
    if not filepath.exists():
        return ""

    file_size = filepath.stat().st_size
    if file_size > MAX_INPUT_SIZE:
        print(f"Error: File too large ({file_size} bytes > {MAX_INPUT_SIZE} limit): {filepath}", file=sys.stderr)
        return ""

    for enc in ENCODING_FALLBACKS:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except (PermissionError, OSError) as e:
            import sys
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            return ""

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except (PermissionError, OSError):
        return ""


def _smart_write_file(filepath: Path, content: str) -> bool:
    """智能写入文件，使用UTF-8编码"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Warning: Failed to write {filepath}: {e}", file=sys.stderr)
        return False

# ---------------------------------------------------------------------------
# Subagent 委派支持
# ---------------------------------------------------------------------------

def create_delegate_message(
    task_type: str,
    input_path: str,
    theme: str = "default",
    output_path: str = None,
    requirements: list = None
) -> str:
    """
    创建Subagent委派消息
    
    Args:
        task_type: 任务类型 (render, generate, optimize)
        input_path: 输入文件路径或内容
        theme: 主题名称
        output_path: 期望的输出路径
        requirements: 额外需求列表
    
    Returns:
        格式化的委派消息字符串
    """
    msg = f"""[MHSWITCH_DELEGATE]
task: {task_type}
input: {input_path}
theme: {theme}"""
    
    if output_path:
        msg += f"\noutput: {output_path}"
    
    default_reqs = [
        "输出.md源文件（供AI阅读和编辑）",
        "输出.html最终文件（供人类阅读）"
    ]
    
    reqs = requirements or default_reqs
    msg += "\nrequirements:"
    for req in reqs:
        msg += f"\n  - {req}"
    
    return msg


def parse_delegate_message(message: str) -> dict:
    """解析委派消息并提取参数"""
    result = {
        "task": None,
        "input": None,
        "theme": "default",
        "output": None,
        "requirements": []
    }
    
    if "[MHSWITCH_DELEGATE]" not in message:
        return result
    
    lines = message.split('\n')
    current_key = None
    
    for line in lines[1:]:
        line = line.strip()
        
        if line.startswith('task:'):
            current_key = 'task'
            result['task'] = line.split(':', 1)[1].strip()
        elif line.startswith('input:'):
            current_key = 'input'
            result['input'] = line.split(':', 1)[1].strip()
        elif line.startswith('theme:'):
            current_key = 'theme'
            result['theme'] = line.split(':', 1)[1].strip()
        elif line.startswith('output:'):
            current_key = 'output'
            result['output'] = line.split(':', 1)[1].strip()
        elif line.startswith('requirements:'):
            current_key = 'requirements'
        elif line.startswith('- ') and current_key == 'requirements':
            result['requirements'].append(line[2:].strip())
    
    return result


def create_result_message(
    status: str,
    files: list,
    issues: list = None,
    stats: dict = None
) -> str:
    """
    创建结果回传消息
    
    Args:
        status: 状态 (success, partial, failed)
        files: 生成的文件路径列表
        issues: 问题列表（如有）
        stats: 统计信息字典
    
    Returns:
        格式化的结果消息字符串
    """
    msg = f"""[MHSWITCH_RESULT]
status: {status}
files:"""
    
    for filepath in files:
        file_info = {"path": filepath}
        
        import os
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            file_info["size"] = size
            file_info["type"] = "markdown" if filepath.endswith('.md') else "html"
        
        msg += f"\n  - path: {filepath}"
        if "size" in file_info:
            msg += f" ({file_info['size']} bytes)"
    
    msg += "\n]"
    
    if issues:
        msg += "\nissues:"
        for issue in issues:
            msg += f"\n  ⚠️ {issue}"
    else:
        msg += "\nissues: []"
    
    if stats:
        msg += "\nstatistics:"
        for key, value in stats.items():
            msg += f"\n  {key}: {value}"
    
    return msg


def execute_delegated_task(delegate_msg: str) -> dict:
    """
    执行Subagent委派的任务
    
    Args:
        delegate_msg: 委派消息字符串
    
    Returns:
        包含执行结果的字典
    """
    params = parse_delegate_message(delegate_msg)
    
    if not params['task'] or not params['input']:
        return {
            "success": False,
            "error": "Invalid delegate message: missing task or input"
        }
    
    try:
        if os.path.exists(params['input']):
            safe_input = _resolve_safe_path(params['input'])
            markdown_content = _detect_and_read_file(safe_input)
        else:
            markdown_content = params['input']

        output_html = params.get('output', 'output.html')
        safe_output = _resolve_safe_path(output_html)
        output_md = str(safe_output).rsplit('.', 1)[0] + '.md' if '.' in str(safe_output) else 'output.md'

        if os.path.exists(params['input']) and params['input'].endswith('.md'):
            output_md = params['input']
        else:
            _smart_write_file(Path(output_md), markdown_content)

        html_result = process(
            markdown_content,
            template=params.get('theme', 'default')
        )

        _smart_write_file(safe_output, html_result)
        
        # 收集统计信息
        stats = {
            "components_used": markdown_content.count(":::") + markdown_content.count("@"),
            "headings_found": len(_document_headings),
            "html_size": len(html_result),
            "markdown_size": len(markdown_content)
        }
        
        # 创建成功结果
        result_msg = create_result_message(
            status="success",
            files=[output_md, output_html],
            stats=stats
        )
        
        return {
            "success": True,
            "message": result_msg,
            "files": [output_md, output_html],
            "stats": stats
        }
        
    except Exception as e:
        error_msg = create_result_message(
            status="failed",
            files=[],
            issues=[f"Execution error: {str(e)}"]
        )
        
        return {
            "success": False,
            "message": error_msg,
            "error": str(e)
        }


def detect_subagent_availability() -> bool:
    """检测Subagent是否可用"""
    import os
    return os.environ.get('SUBAGENT_AVAILABLE', '').lower() in ('true', '1', 'yes')


def suggest_workflow(has_markdown_file: bool = False, content_complexity: str = "medium") -> str:
    """
    根据当前状态建议最佳工作流
    
    Args:
        has_markdown_file: 是否已有Markdown文件
        content_complexity: 内容复杂度 (simple, medium, complex)
    
    Returns:
        工作流建议文本
    """
    subagent_available = detect_subagent_availability()
    
    if has_markdown_file:
        if subagent_available:
            return """建议：委托Subagent执行

工作流：
1. 主Agent创建委派消息
2. Subagent接收并执行渲染命令
3. Subagent回传结果给主Agent

命令示例：
python scripts/render.py --file <input.md> --output <output.html>"""
        else:
            return """建议：主Agent直接执行

工作流：
1. 读取现有Markdown文件
2. 执行渲染命令生成HTML

命令：
python scripts/render.py --file <input.md> --output <output.html>"""
    
    else:
        if subagent_available and content_complexity in ('medium', 'complex'):
            return """建议：协作模式

工作流：
1. 主Agent根据需求生成优化的Markdown
2. 保存为临时.md文件
3. 委托Subagent执行渲染和优化
4. Subagent返回最终HTML文件

优势：
- 并行处理提升效率
- 分离关注点降低错误率
- 更好的错误隔离"""
        else:
            return """建议：主Agent全流程处理

工作流：
1. 分析用户需求
2. 生成适合HTML展示的Markdown
3. 执行渲染命令"""


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parent.parent

_SAFE_ROOTS = [SKILL_ROOT]


def _resolve_safe_path(path_str: str) -> Path:
    """解析路径并验证其是否在安全目录内。

    将相对路径解析到 SKILL_ROOT 下，拒绝路径遍历尝试。
    """
    import os as _os

    raw = Path(path_str)

    if raw.is_absolute():
        resolved = raw.resolve()
        for root in _SAFE_ROOTS:
            try:
                resolved.relative_to(root.resolve())
                return resolved
            except ValueError:
                continue
        raise ValueError(f"路径不在允许的目录内: {path_str}")
    else:
        resolved = (SKILL_ROOT / raw).resolve()
        try:
            resolved.relative_to(SKILL_ROOT.resolve())
            return resolved
        except ValueError:
            raise ValueError(f"路径穿越被拒绝: {path_str}")


def _resolve_unsafe_path(path_str: str) -> Path:
    """不安全的路径解析（向后兼容，不检查边界）"""
    return Path(path_str)

# ---------------------------------------------------------------------------
# 阶段 1: Front Matter 解析
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_front_matter(text: str) -> tuple[Dict[str, Any], str]:
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, text[m.end():]

# ---------------------------------------------------------------------------
# 阶段 2: Widget 展开
# ---------------------------------------------------------------------------

_WIDGET_ALIASES = {
    'milestone': 'milestone-card',
    'status': 'status-report',
    'toc': 'table-of-contents',
    'kbd': 'keyboard',
    'img': 'image',
    'vid': 'video',
    'fig': 'figure',
    'btn': 'button',
    'badge': 'badge',
    'tag': 'badge',
    'tip': 'callout',
    'warn': 'alert',
    'warning': 'alert',
    'err': 'alert',
    'error': 'alert',
    'info': 'alert',
    'note': 'callout',
    'col': 'columns',
    'step': 'steps',
    'feat': 'features',
    'tab': 'tabs',
    'panel': 'side-panel',
    'diag': 'diagram',
    'chart': 'chart',
    'bar': 'chart',
    'pie': 'chart',
    'line': 'chart',
    'stat': 'stats',
    'kpi': 'kpi-row',
    'hero': 'hero',
    'modal': 'modal-dialog',
    'dialog': 'modal-dialog',
    'kan': 'kanban',
    'board': 'kanban',
    'map': 'mindmap',
    'tree': 'mindmap',
    'rec': 'recommendation',
    'drag': 'drag-card',
    'term': 'terminal',
    'code': 'terminal',
    'prompt': 'ai-prompt',
    'ai': 'ai-prompt',
    'quote': 'blockquote',
    'block': 'blockquote',
    'detail': 'details',
    'accordion': 'details',
    'grid': 'grid',
    'cols': 'columns',
    'comp': 'comparison',
    'compare': 'comparison',
    'time': 'timeline',
    'carry': 'carryover',
    'velo': 'velocity-chart',
    'velocity': 'velocity-chart',
    'exploration': 'explorations',
    'exp': 'explorations',
    'hl': 'highlights',
    'highlight': 'highlights',
    'open-q': 'open-question',
    'question': 'open-question',
    'svg': 'svg-figure',
}

def _resolve_widget_name(name: str, widget_defs: dict) -> str:
    """Resolve widget name using aliases or return original if found in defs"""
    if name in widget_defs:
        return name
    alias = _WIDGET_ALIASES.get(name.lower())
    if alias and alias in widget_defs:
        return alias
    return name

_FENCE_WIDGET_RE = re.compile(
    r":::(\w+)(?:\{((?:[^{}]|\{[^{}]*\})*)\})?\s*\n(.*?)\n\s*:::", re.DOTALL
)

_INLINE_WIDGET_RE = re.compile(r'@(\w[\w-]*)(?:\[([^\]]*)\])?(?:\{((?:[^{}]|\{[^{}]*\})*)\})?(?:\(([^\)]*)\))?')


def _restore_placeholders(text: str) -> str:
    """将占位符恢复为原始内容"""
    import re as re_module
    
    for prefix in ('MHSWITCH_INLINE_', 'MHSWITCH_FENCE_'):
        matches = list(re_module.finditer(rf'{re_module.escape(prefix)}(\d+)_', text))
        for match in reversed(matches):
            idx = int(match.group(1))
            if idx < len(_code_blocks_for_restore):
                original = _code_blocks_for_restore[idx][3]
                text = text[:match.start()] + original + text[match.end():]
    
    return text


_code_blocks_for_restore = []


def _parse_attrs(raw: str) -> Dict[str, str]:
    import html as html_module
    import re as re_module
    global _code_blocks_for_restore
    attrs: Dict[str, str] = {}
    if not raw.strip():
        return attrs
    
    raw_copy = raw
    
    matches = list(re_module.finditer(r'MHSWITCH_INLINE_(\d+)_', raw_copy))
    for m in reversed(matches):
        idx = int(m.group(1))
        if idx < len(_code_blocks_for_restore):
            original = _code_blocks_for_restore[idx][3]
            raw_copy = raw_copy[:m.start()] + original + raw_copy[m.end():]
    
    raw = raw_copy.replace("\\{", "{").replace("\\}", "}").strip()

    decoded_raw = html_module.unescape(raw)

    key_value_pattern = re_module.compile(r"(\w+)\s*=\s*(?:\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')", re.DOTALL)
    for m in key_value_pattern.finditer(decoded_raw):
        value = m.group(2) if m.group(2) is not None else m.group(3)
        value = value.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
        value = value.replace('\\"', '"').replace("\\'", "'")
        attrs[m.group(1)] = value
    
    return attrs


# ============================================================================
# Widget Content Handler Registry
# ============================================================================

_WIDGET_HANDLERS = {}


def _restore_terminal_entities(text: str) -> str:
    text = text.replace('=&gt;', '⇒')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('⇒', '=>')
    return text

def _register_handler(name: str):
    def decorator(fn):
        _WIDGET_HANDLERS[name] = fn
        return fn
    return decorator


@_register_handler("terminal")
def _handle_terminal(merged, processed_content, attrs, md_converter, widget_defs):
    global _code_blocks_for_restore
    import html as html_module
    import re as re_module

    content_original = processed_content

    if _code_blocks_for_restore:
        for idx, item in enumerate(_code_blocks_for_restore):
            content_original = content_original.replace(f"MHSWITCH_INLINE_{idx}_", item[3])
            content_original = content_original.replace(f"MHSWITCH_FENCE_{idx}_", item[3])

    content_original = content_original.replace('&grave;', '`')
    content_original = _restore_terminal_entities(content_original)

    _lang_name_map = {
        'javascript': 'javascript', 'js': 'javascript',
        'typescript': 'typescript', 'ts': 'typescript',
        'python': 'python', 'py': 'python',
        'bash': 'bash', 'sh': 'bash', 'shell': 'bash',
        'json': 'json',
        'html': 'html', 'htm': 'html',
        'css': 'css',
        'sql': 'sql',
        'java': 'java',
        'c': 'c', 'cpp': 'cpp', 'c++': 'cpp', 'cc': 'cpp',
        'go': 'go',
        'rust': 'rust', 'rs': 'rust',
        'ruby': 'ruby', 'rb': 'ruby',
        'php': 'php',
        'swift': 'swift',
        'kotlin': 'kotlin', 'kt': 'kotlin',
        'scala': 'scala',
        'r': 'r',
        'lua': 'lua',
        'perl': 'perl', 'pl': 'perl',
        'xml': 'xml',
        'yaml': 'yaml', 'yml': 'yaml',
        'markdown': 'markdown', 'md': 'markdown',
        'dockerfile': 'docker', 'docker': 'docker',
        'plaintext': 'text', 'text': 'text',
    }

    fence_match = re_module.match(r'^```\s*(\S*)\s*\n(.*?)^```$', content_original, re_module.DOTALL)
    if fence_match:
        lang = fence_match.group(1).strip()
        code_content = fence_match.group(2)
        if not lang:
            title = merged.get("title", "")
            if title:
                import os.path as _os_path
                _, ext = _os_path.splitext(title)
                if not ext:
                    lang = _lang_name_map.get(title.lower(), '')
                else:
                    ext = ext.lower()
                    lang = {'.js':'javascript','.ts':'typescript','.py':'python','.sh':'bash','.json':'json','.html':'html','.css':'css'}.get(ext, '')
            if not lang and code_content:
                lang = 'plaintext'
    else:
        code_content = content_original
        title = merged.get("title", "")
        lang = ""
        if title:
            import os.path as _os_path
            _, ext = _os_path.splitext(title)
            ext = ext.lower()
            lang = {'.js':'javascript','.ts':'typescript','.py':'python','.sh':'bash','.json':'json','.html':'html','.css':'css'}.get(ext, '')
        if not lang:
            lang = _lang_name_map.get(title.lower(), '')

    def _escape_markdown_in_terminal(text: str) -> str:
        text = html_module.escape(text)
        text = text.replace('#', '&#35;')
        text = re.sub(r'^( {0,3})([-*+])', lambda m: m.group(1) + '&#' + str(ord(m.group(2))) + ';', text, flags=re.MULTILINE)
        text = re.sub(r'^( {0,3})(\d+)\.', r'\1\2&#46;', text, flags=re.MULTILINE)
        return text

    if lang:
        highlighted = _highlight_code(lang, code_content)
        if highlighted:
            merged["content"] = highlighted
        else:
            merged["content"] = f'<pre class="mhs-terminal-pre">{_escape_markdown_in_terminal(code_content)}</pre>'
    else:
        merged["content"] = f'<pre class="mhs-terminal-pre">{_escape_markdown_in_terminal(code_content)}</pre>'

    return merged["content"]


@_register_handler("columns")
def _handle_columns(merged, processed_content, attrs, md_converter, widget_defs):
    import re as re_module
    
    expanded_content = processed_content
    for placeholder, html in _widget_store:
        expanded_content = expanded_content.replace(placeholder, html)
    
    parts = re_module.split(r"\n---\n", expanded_content, flags=re_module.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]
    
    if len(parts) <= 1:
        try:
            col_count = int(merged.get("cols", "2"))
        except (ValueError, TypeError):
            col_count = 2
        
        def extract_cards(html_content):
            cards = []
            card_start_pattern = re_module.compile(r'<div class="mhs-card[^>]*?>')
            matches = list(card_start_pattern.finditer(html_content))
            
            for i, match in enumerate(matches):
                start = match.start()
                if i < len(matches) - 1:
                    next_start = matches[i + 1].start()
                    cards.append(html_content[start:next_start].strip())
                else:
                    cards.append(html_content[start:].strip())
            return cards
        
        cards = extract_cards(expanded_content)
        
        if cards:
            cards_per_col = (len(cards) + col_count - 1) // col_count
            parts = []
            for i in range(col_count):
                start = i * cards_per_col
                end = start + cards_per_col
                parts.append("\n".join(cards[start:end]))
        else:
            parts = [processed_content]
    
    cols_html = []
    for i, part in enumerate(parts):
        if re_module.search(r'<div class="mhs-[a-z]', part):
            col_content = part
        else:
            terminal_pattern = re_module.compile(r'(<div class="mhs-terminal".*?</div>)', re.DOTALL)
            terminal_parts = terminal_pattern.split(part)
            processed_parts = []
            for tp in terminal_parts:
                if terminal_pattern.match(tp):
                    processed_parts.append(tp)
                elif md_converter:
                    processed_parts.append(md_converter(tp))
                else:
                    processed_parts.append(tp)
            col_content = ''.join(processed_parts)
        col_content = col_content.replace('<p></p>', '')
        cols_html.append(f'<div class="mhs-col">{col_content}</div>')
    
    return "\n".join(cols_html)


@_register_handler("toc")
def _handle_toc(merged, processed_content, attrs, md_converter, widget_defs):
    global _document_headings
    toc_items = []
    for h in _document_headings:
        indent = '  ' * (h['level'] - 1) if h['level'] > 1 else ''
        label_clean = re.sub(r'<[^>]+>', '', h["label"]).strip()
        toc_items.append(f'{indent}- [{label_clean}](#{h["slug"]})')
    toc_md = '\n'.join(toc_items) if toc_items else '(无标题)'
    return md_converter(toc_md)


@_register_handler("mindmap")
def _handle_mindmap(merged, processed_content, attrs, md_converter, widget_defs):
    lines = processed_content.split('\n')
    result_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        spaces = '  ' + ('  ' * (indent // 2))
        result_lines.append(spaces + stripped)

    return '\n'.join(result_lines)


@_register_handler("tabs")
def _handle_tabs(merged, processed_content, attrs, md_converter, widget_defs):
    import re as _re_tabs
    # Split content by ---- or --- separator to get tab panels
    # Use flexible pattern: 3 or more dashes (markdown hr is ---, original is ----)
    parts = _re_tabs.split(r'\n-{3,}\s*\n', processed_content.strip())
    parts = [p.strip() for p in parts if p.strip()]
    
    tab_headers = []
    tab_panels = []
    
    for part in parts:
        # First line (usually **bold** or similar) is the tab header
        lines = part.split('\n')
        header_line = ''
        content_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not header_line and stripped:
                header_line = stripped
                # Skip this line from content
                continue
            content_lines.append(line)
        
        # Convert header to HTML
        if md_converter and header_line:
            header_html = md_converter(header_line)
            header_html = _re_tabs.sub(r'^<p>|</p>\n?$', '', header_html)
        else:
            header_html = header_line
        
        tab_headers.append(f'<button class="mhs-tab-btn">{header_html}</button>')
        
        # Convert panel content to HTML
        panel_content = '\n'.join(content_lines).strip()
        if md_converter and panel_content:
            panel_html = md_converter(panel_content)
        else:
            panel_html = panel_content
        
        tab_panels.append(f'<div class="mhs-tab-panel">{panel_html}</div>')
    
    merged["tabs"] = '\n'.join(tab_headers)
    merged["panels"] = '\n'.join(tab_panels)
    
    return ''  # Content is in {{tabs}} and {{panels}} placeholders


@_register_handler("recommendation")
def _handle_recommendation(merged, processed_content, attrs, md_converter, widget_defs):
    import re as _re_rec
    lines = [l.strip() for l in processed_content.split('\n') if l.strip()]
    rec_parts = []
    for line in lines:
        line_html = md_converter(line)
        line_html = _re_rec.sub(r"^<p>|</p>$", "", line_html)
        rec_parts.append(f'<p class="mhs-rec-item">{line_html}</p>')
    return '\n'.join(rec_parts) if rec_parts else processed_content


@_register_handler("eval")
def _handle_eval(merged, processed_content, attrs, md_converter, widget_defs):
    code = processed_content.strip()
    merged["code"] = code

    if not _EVAL_ALLOWED:
        merged["result"] = "❌ eval 组件已禁用（使用 --allow-eval 启用）"
        return processed_content

    try:
        result = _safe_eval_expression(code)
        result_str = str(result) if result is not None else ""
        merged["result"] = result_str
    except Exception as e:
        merged["result"] = f"❌ {type(e).__name__}: {str(e)}"

    return processed_content


def _safe_eval_expression(code: str):
    import re as re_module

    normalized = code.replace(' ', '').replace('\t', '').replace('\n', '').lower()
    dangerous_keywords = [
        'import', 'exec', 'eval', 'compile', 'open', 'file',
        '__import__', '__builtins__', '__builtin__',
        '__class__', '__bases__', '__mro__', '__subclasses__',
        '__globals__', '__code__', '__func__', '__self__',
        '__dict__', '__module__', '__getattribute__',
        'globals()', 'locals()', 'vars()',
        'getattr', 'setattr', 'delattr',
        'breakpoint', 'input',
        'os.', 'sys.',
        'subprocess', 'shutil', 'pathlib', 'socket',
        'write(', 'read(',
    ]
    for kw in dangerous_keywords:
        if kw in normalized:
            raise ValueError("不安全的表达式")

    MAX_EXPR_LENGTH = 200
    if len(code) > MAX_EXPR_LENGTH:
        raise ValueError("表达式过长")

    safe_builtins = {
        'True': True, 'False': False, 'None': None,
        'abs': abs, 'all': all, 'any': any, 'bool': bool,
        'chr': chr, 'complex': complex, 'dict': dict,
        'float': float, 'hash': hash, 'hex': hex, 'int': int,
        'isinstance': isinstance, 'len': len, 'list': list,
        'max': max, 'min': min, 'oct': oct, 'ord': ord,
        'pow': pow, 'range': range, 'round': round, 'set': set,
        'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
        'enumerate': enumerate, 'filter': filter, 'map': map,
        'zip': zip, 'sorted': sorted, 'reversed': reversed,
        'divmod': divmod, 'bin': bin, 'iter': iter, 'next': next,
    }

    cleaned = code.strip()
    if '\n' in cleaned:
        cleaned = ' '.join(line.strip() for line in cleaned.split('\n') if line.strip())

    import threading

    result_container = [None]
    error_container = [None]

    def _run():
        try:
            result_container[0] = eval(cleaned, {'__builtins__': safe_builtins}, {})
        except Exception as e:
            error_container[0] = e

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=1)

    if error_container[0]:
        raise error_container[0]
    if thread.is_alive():
        raise TimeoutError("执行超时")

    return result_container[0]


def _render_widget(
    name: str,
    wdef: dict,
    content: str,
    attrs: Dict[str, str],
    md_converter=None,
    widget_defs=None,
) -> str:
    merged = dict(wdef.get("defaults", {}))
    merged.update(attrs)

    if widget_defs:
        for k, v in list(merged.items()):
            if isinstance(v, str) and '@' in v and _INLINE_WIDGET_RE.search(v):
                expanded = _expand_inline_widgets_direct(v, widget_defs, md_converter)
                if expanded != v:
                    merged[k] = expanded

    if content.strip():
        if name == "progress" and not merged.get("percent"):
            merged["percent"] = content.strip()
        elif name not in ("card", "alert", "details", "quote", "callout",
                           "steps", "stats", "features", "tabs", "timeline",
                           "kanban", "grid", "hero", "chart", "highlights",
                           "velocity-chart", "carryover", "explorations",
                           "prompt", "prompt-block", "recommendation",
                           "modal", "panel", "svg", "status-report",
                           "kpi-row", "open-question", "eval",
                           "timeitem", "ticket", "carryover-item",
                           "drag-card", "input-group", "mermaid",
                           "mindmap", "numbered-section", "milestone-card"):
            merged["content"] = content.strip()

    if name == "comparison-row":
        pro_text = attrs.get('pro', '') or merged.get('pro', '')
        con_text = attrs.get('con', '') or merged.get('con', '')

        def _conv_cell(text):
            if not text:
                return ''
            lines = text.split('\n')
            if md_converter:
                converted = [md_converter(line.strip()) for line in lines if line.strip()]
                converted = [re.sub(r'^<p>|</p>\n?$', '', c) for c in converted]
                return '<br>'.join(converted)
            else:
                return '<br>'.join(l.strip() for l in lines if l.strip())

        return f'<div class="mhs-comparison-row"><div class="pro-cell">{_conv_cell(pro_text)}</div><div class="con-cell">{_conv_cell(con_text)}</div></div>'

    if md_converter and content.strip():
        processed_content = content.strip()
        handler = _WIDGET_HANDLERS.get(name)
        if handler:
            merged["content"] = handler(merged, processed_content, attrs, md_converter, widget_defs)
        else:
            content_to_render = processed_content
            if widget_defs:
                content_to_render = expand_inline_widgets(content_to_render, widget_defs, md_converter)
            html_content = md_converter(content_to_render)
            is_inline = wdef.get("syntax") == "inline"
            if is_inline:
                html_content = re.sub(r"^<p>|</p>\n?$", "", html_content)
            merged["content"] = html_content
    elif not merged.get("content"):
        import html as _html_mod
        merged["content"] = _html_mod.escape(content.strip())

    tmpl = wdef.get("template")
    if tmpl is None:
        return f"<!-- Widget {name}: missing template -->"

    # 处理条件块：{{#if key}}...{{/if}}
    def _resolve_conditionals(t: str) -> str:
        # {{#if key}}...{{/if}}
        def _if_sub(m: re.Match) -> str:
            key = m.group(1).strip()
            inner = m.group(2)
            return inner if merged.get(key) else ''
        t = re.sub(r'\{\{#if\s+(\w[\w-]*)\s*\}\}(.*?)\{\{/if\}\}', _if_sub, t, flags=re.DOTALL)

        # {{#unless key}}...{{/unless}}
        def _unless_sub(m: re.Match) -> str:
            key = m.group(1).strip()
            inner = m.group(2)
            return inner if not merged.get(key) else ''
        t = re.sub(r'\{\{#unless\s+(\w[\w-]*)\s*\}\}(.*?)\{\{/unless\}\}', _unless_sub, t, flags=re.DOTALL)

        # {{#equals key "value"}}...{{/equals}}
        def _equals_sub(m: re.Match) -> str:
            key = m.group(1).strip()
            expected = m.group(2).strip().strip('"\'')
            inner = m.group(3)
            actual = str(merged.get(key, ''))
            return inner if actual == expected else ''
        t = re.sub(r'\{\{#equals\s+(\w[\w-]*)\s+"([^"]*)"\s*\}\}(.*?)\{\{/equals\}\}', _equals_sub, t, flags=re.DOTALL)
        t = re.sub(r"\{\{#equals\s+(\w[\w-]*)\s+'([^']*)'\s*\}\}(.*?)\{\{/equals\}\}", _equals_sub, t, flags=re.DOTALL)

        # {{#each items}}...{{/each}} — 迭代列表（逗号分隔）
        def _each_sub(m: re.Match) -> str:
            key = m.group(1).strip()
            inner = m.group(2)
            items_str = str(merged.get(key, ''))
            if not items_str:
                return ''
            items = [item.strip() for item in items_str.split(',') if item.strip()]
            result_parts = []
            for item in items:
                item_html = inner.replace('{{item}}', item)
                result_parts.append(item_html)
            return ''.join(result_parts)
        t = re.sub(r'\{\{#each\s+(\w[\w-]*)\s*\}\}(.*?)\{\{/each\}\}', _each_sub, t, flags=re.DOTALL)

        return t

    tmpl = _resolve_conditionals(tmpl)
    for _ in range(10):
        prev = tmpl
        tmpl = _resolve_conditionals(tmpl)
        if tmpl == prev:
            break

    def _sub(m: re.Match) -> str:
        key = m.group(1).strip()
        val = str(merged.get(key, m.group(0)))
        if md_converter and val and '<' not in val and re.search(r'(\*\*|`[^`]+`|\n)', val):
            # Skip markdown conversion for content that looks like code/mermaid/raw syntax
            # (starts with common code-like patterns or is the 'content' key for special widgets)
            _is_raw_content = (
                key == 'content' and name in ('mindmap', 'mermaid', 'svg', 'eval') or
                val.lstrip().startswith(('#', '$', '>', '|', 'mindmap', 'graph', 'sequenceDiagram', 'gantt', 'classDiagram', 'gitgraph', 'pie', 'quadrantChart'))
            )
            if not _is_raw_content:
                converted = md_converter(val)
                converted = re.sub(r'^<p>|</p>\n?$', '', converted)
                return converted
        return val

    result = re.sub(r"\{\{\s*(\w[\w-]*)\s*\}\}", _sub, tmpl)
    result = result.replace(' href=""', '')
    
    if name == "terminal":
        result = _restore_terminal_entities(result)

    return result


def expand_inline_widgets(
    text: str,
    widget_defs: Dict[str, Any],
    md_converter=None,
) -> str:
    """展开文本中的所有内联组件"""
    global _widget_store
    if not hasattr(expand_inline_widgets, '_counter'):
        expand_inline_widgets._counter = 0
    
    def _inline_replacer(m: re.Match) -> str:
        name = m.group(1)
        body_text = m.group(2) or ""
        attrs_str = m.group(3) or ""
        paren_text = m.group(4) or ""

        name = _resolve_widget_name(name, widget_defs)
        wdef = widget_defs.get(name)
        if not wdef or wdef.get("syntax") != "inline":
            return m.group(0)

        if body_text.startswith('MHSWITCH_'):
            return m.group(0)

        if body_text and not body_text.startswith('{'):
            if "=" in body_text:
                attrs = _parse_attrs(body_text)
                body = ""
            else:
                attrs = _parse_attrs(attrs_str) if attrs_str else {}
                body = body_text
        else:
            attrs = _parse_attrs(attrs_str) if attrs_str else {}
            body = body_text

        if not attrs and paren_text:
            attrs = _parse_attrs(paren_text)

        html = _render_widget(name, wdef, body, attrs, md_converter, widget_defs)
        placeholder = f"MHSWITCH_PH_{expand_inline_widgets._counter}_"
        _widget_store.append((placeholder, html))
        expand_inline_widgets._counter += 1
        return placeholder
    
    result = _INLINE_WIDGET_RE.sub(_inline_replacer, text)
    return result


def _expand_inline_widgets_direct(
    text: str,
    widget_defs: Dict[str, Any],
    md_converter=None,
) -> str:
    global _widget_store
    if not hasattr(expand_inline_widgets, '_counter'):
        expand_inline_widgets._counter = 0

    def _direct_replacer(m: re.Match) -> str:
        name = m.group(1)
        body_text = m.group(2) or ""
        attrs_str = m.group(3) or ""
        paren_text = m.group(4) or ""

        name = _resolve_widget_name(name, widget_defs)
        wdef = widget_defs.get(name)
        if not wdef or wdef.get("syntax") != "inline":
            return m.group(0)

        if body_text.startswith('MHSWITCH_'):
            return m.group(0)

        if body_text and not body_text.startswith('{'):
            if "=" in body_text:
                attrs = _parse_attrs(body_text)
                body = ""
            else:
                attrs = _parse_attrs(attrs_str) if attrs_str else {}
                body = body_text
        else:
            attrs = _parse_attrs(attrs_str) if attrs_str else {}
            body = body_text

        if not attrs and paren_text:
            attrs = _parse_attrs(paren_text)

        base_count = len(_widget_store)
        html = _render_widget(name, wdef, body, attrs, md_converter, widget_defs)

        for i in range(base_count, len(_widget_store)):
            ph, val = _widget_store[i]
            html = html.replace(ph, val)

        return html

    result = _INLINE_WIDGET_RE.sub(_direct_replacer, text)
    return result


def expand_inline_widgets_in_html(
    html_content: str,
    widget_defs: Dict[str, Any],
) -> str:
    """在HTML内容中展开内联组件（用于columns等已经转换过markdown的内容）"""
    
    def _html_inline_replacer(m: re.Match) -> str:
        name = m.group(1)
        content_or_attrs = m.group(2) or ""
        link = m.group(3) or ""
        extra_attrs = m.group(4) or ""
        
        name = _resolve_widget_name(name, widget_defs)
        wdef = widget_defs.get(name)
        if not wdef:
            return m.group(0)
            
        if wdef.get("syntax") != "inline":
            return m.group(0)
        
        if content_or_attrs.startswith('MHSWITCH_'):
            return m.group(0)
        
        if content_or_attrs and not content_or_attrs.startswith('{'):
            if "=" in content_or_attrs:
                attrs = _parse_attrs(content_or_attrs)
                body = ""
            else:
                attrs = _parse_attrs(extra_attrs) if extra_attrs else {}
                body = content_or_attrs
        else:
            attrs = _parse_attrs(extra_attrs) if extra_attrs else {}
            body = content_or_attrs
        
        if link:
            attrs["href"] = link
        
        if extra_attrs:
            attrs.update(_parse_attrs(extra_attrs))
        
        html = _render_widget(name, wdef, body, attrs, None, widget_defs)
        return html
    
    result = _INLINE_WIDGET_RE.sub(_html_inline_replacer, html_content)
    return result


def expand_widgets(
    text: str,
    widget_defs: Dict[str, Any],
    md_converter=None,
) -> str:
    """主解析入口 - 完全重写以支持深层嵌套"""
    global _widget_store
    _widget_store = []
    _counter_local = [0]
    _original_text = text

    def _get_next_id():
        res = _counter_local[0]
        _counter_local[0] += 1
        return f"MHSWITCH_PH_{res}_"

    def find_fence_end(text: str, start: int) -> int:
        depth = 1
        i = start
        while i < len(text):
            pos = text.find(':::', i)
            if pos == -1: return -1
            
            line_start = text.rfind('\n', 0, pos) + 1
            line_end = text.find('\n', pos)
            if line_end == -1: line_end = len(text)
            line_text = text[line_start:line_end].strip()
            
            if line_text == ":::" or line_text == "::::":
                depth -= 1
                if depth == 0: return pos
                i = pos + len(line_text)
            elif line_text.startswith(":::") and not (line_text == ":::" or line_text == "::::"):
                depth += 1
                i = pos + len(line_text)
            else:
                i = pos + 3
        return -1

    def _parse_and_store_inline(m: re.Match, original_text: str = None) -> str:
        name = m.group(1)
        c1 = m.group(2) or ""  # [...] body
        c2 = m.group(3) or ""  # {...} attrs
        c3 = m.group(4) or ""  # (...) paren attrs

        body = c1
        attrs = {}

        if c2:
            attrs = _parse_attrs(c2)
        if not attrs and c3:
            attrs = _parse_attrs(c3)

        name = _resolve_widget_name(name, widget_defs)
        wdef = widget_defs.get(name)
        if not wdef: return m.group(0)

        html = _render_widget(name, wdef, body, attrs, md_converter, widget_defs)
        placeholder = _get_next_id()
        _widget_store.append((placeholder, html))
        return placeholder

    MAX_RECURSION_DEPTH = 20

    def _recursive_parse(txt: str, depth: int = 0) -> str:
        if depth > MAX_RECURSION_DEPTH:
            raise RecursionError(f"Widget 嵌套层数超过限制 ({MAX_RECURSION_DEPTH})，可能存在循环引用")

        start_pattern = re.compile(r'^\s*:{3,4}(\w[\w-]*)(?:\{((?:[^{}]|\{[^{}]*\})*)\})?', re.MULTILINE)

        res_parts = []
        curr_pos = 0

        while curr_pos < len(txt):
            m = start_pattern.search(txt, curr_pos)
            if not m:
                remaining = txt[curr_pos:]
                processed = _INLINE_WIDGET_RE.sub(
                    lambda mo: _parse_and_store_inline(mo, _original_text), remaining
                )
                res_parts.append(processed)
                break
            
            pre_text = txt[curr_pos:m.start()]
            res_parts.append(_INLINE_WIDGET_RE.sub(
                lambda mo: _parse_and_store_inline(mo, _original_text), pre_text
            ))
            
            name = m.group(1)
            attrs_str = m.group(2) or ""
            
            line_end = txt.find('\n', m.end())
            if line_end == -1: line_end = len(txt)
            line_content = txt[m.start():line_end].strip()
            
            # 单行 :::name{...}:::
            if line_content.endswith(':::') and line_content != ':::':
                name = _resolve_widget_name(name, widget_defs)
                wdef = widget_defs.get(name)
                if wdef:
                    html = _render_widget(name, wdef, "", _parse_attrs(attrs_str), md_converter, widget_defs)
                    ph = _get_next_id()
                    _widget_store.append((ph, html))
                    res_parts.append(f"\n\n{ph}\n\n")
                else:
                    res_parts.append(txt[m.start():line_end])
                curr_pos = line_end + 1
                continue

            # 单行无闭合 :::name{attrs}（属性包含所有内容，无需 body）
            # 检查下一行是否是另一个组件或空行，如果是则视为自闭合
            _next_line_start = line_end + 1
            if _next_line_start < len(txt):
                # Skip empty lines to find the real next content
                _search_pos = _next_line_start
                while _search_pos < len(txt):
                    _next_line_end = txt.find('\n', _search_pos)
                    if _next_line_end == -1:
                        _next_line_end = len(txt)
                    _next_line = txt[_search_pos:_next_line_end].strip()
                    if _next_line:  # Found non-empty line
                        break
                    _search_pos = _next_line_end + 1
                else:
                    _next_line = ''
                
                # 判断是否为自闭合组件：
                # - 下一行为空 → 自闭合
                # - 下一行是标题(#)/分割线(---)/HTML标签(<) → 自闭合
                # - 下一行是独立的 ::: 或 :::: 闭合标记 → 自闭合
                # - 下一行是 :::name{...} 形式的嵌套组件 → 非自闭合（有嵌套内容）
                import re as _re_sc
                _is_closing_fence_only = bool(_re_sc.match(r'^:{3,4}\s*$', _next_line))
                _is_nested_widget_open = bool(_re_sc.match(r'^:{3,4}[\w[].*', _next_line))
                _is_self_closing = (
                    not _next_line or 
                    _next_line.startswith('#') or 
                    _next_line.startswith('---') or
                    (_is_closing_fence_only and not _is_nested_widget_open)
                )
                if _is_self_closing:
                    name = _resolve_widget_name(name, widget_defs)
                    wdef = widget_defs.get(name)
                    if wdef:
                        html = _render_widget(name, wdef, "", _parse_attrs(attrs_str), md_converter, widget_defs)
                        ph = _get_next_id()
                        _widget_store.append((ph, html))
                        res_parts.append(f"\n\n{ph}\n\n")
                    else:
                        res_parts.append(txt[m.start():line_end])
                    curr_pos = line_end + 1
                    continue
            
            # 多行
            content_start = line_end + 1
            end_pos = find_fence_end(txt, content_start)
            
            if end_pos == -1:
                res_parts.append(txt[m.start():m.end()])
                curr_pos = m.end()
                continue
            
            body = txt[content_start:end_pos].strip('\r\n')
            # 递归处理 body，但terminal组件不需要递归处理，因为它包含代码
            if name == "terminal":
                body_processed = body
            else:
                # Protect ::: patterns inside code blocks before recursive parsing
                # to prevent false widget matches causing infinite recursion
                _protected_body = body
                _code_protection_store = []
                
                # Protect fenced code blocks (``` ... ```)
                import re as _re
                def _protect_fence(m):
                    placeholder = f"MHSWITCH_CODE_PROT_{len(_code_protection_store)}_"
                    _code_protection_store.append(m.group(0))
                    return placeholder
                _protected_body = _re.sub(r'^```[\s\S]*?^```', _protect_fence, _protected_body, flags=_re.MULTILINE)
                
                # Protect inline code (` ... `)
                def _protect_inline(m):
                    placeholder = f"MHSWITCH_CODE_PROT_{len(_code_protection_store)}_"
                    _code_protection_store.append(m.group(0))
                    return placeholder
                _protected_body = _re.sub(r'``((?:[^`]|`(?!`))+?)``', _protect_inline, _protected_body)
                _protected_body = _re.sub(r'`([^`\n]+)`', _protect_inline, _protected_body)
                
                body_processed = _recursive_parse(_protected_body, depth + 1)
                
                # Restore protected code blocks
                for i, original in enumerate(_code_protection_store):
                    body_processed = body_processed.replace(f"MHSWITCH_CODE_PROT_{i}_", original)
            
            name = _resolve_widget_name(name, widget_defs)
            wdef = widget_defs.get(name)
            if not wdef:
                print(f"WARN: Widget {name} not found in defs!")
                res_parts.append(f":::{name}{{{attrs_str}}}\n{body_processed}\n:::")
            else:
                html = _render_widget(name, wdef, body_processed, _parse_attrs(attrs_str), md_converter, widget_defs)
                ph = _get_next_id()
                _widget_store.append((ph, html))
                res_parts.append(f"\n\n{ph}\n\n")
            
            # 跳过该块
            after_close = txt.find('\n', end_pos + 3)
            curr_pos = after_close + 1 if after_close != -1 else len(txt)
        
        result = "".join(res_parts)

        return result

    result = _recursive_parse(text)

    terminal_pattern = re.compile(r'<div class="mhs-terminal-body">.*?</div>', re.DOTALL)
    result = terminal_pattern.sub(lambda m: _restore_terminal_entities(m.group(0)), result)

    # 清理残留的 ::: 闭合标记（未被组件解析器消费的情况）
    result = re.sub(r'<p>\s*:::\s*</p>\s*\n?', '', result)
    # 也处理单独一行的 :::
    result = re.sub(r'^\s*:::\s*$\n?', '', result, flags=re.MULTILINE)

    return result

# ---------------------------------------------------------------------------
# Widget 定义加载
# ---------------------------------------------------------------------------

def load_widget_defs(path: Optional[str] = None) -> Dict[str, Any]:
    if path is None:
        path = str(SKILL_ROOT / "references" / "widgets.json")
    
    content = _detect_and_read_file(Path(path))
    if not content:
        return {}
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in {path}", file=sys.stderr)
        return {}

# ---------------------------------------------------------------------------
# 阶段 3: Markdown → HTML
# ---------------------------------------------------------------------------

def markdown_to_html(text: str, collect_headings: bool = True) -> str:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
    from markdown_it.common.utils import escapeHtml
    import re
    import unicodedata

    md = MarkdownIt("gfm-like", {
        "html": True,
        "breaks": False,
        "linkify": False,
        "typographer": True,
    })

    def slugify(text: str) -> str:
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'^-+|-+$', '', text)
        return text or 'section'

    def heading_open_renderer(tokens, idx, options, env):
        token = tokens[idx]
        level = token.tag[1]
        
        label = ''
        for i in range(idx + 1, len(tokens)):
            if tokens[i].type in ('heading_open', 'heading_close'):
                break
            if tokens[i].type == 'inline':
                label = tokens[i].content
                break
        
        custom_id = None
        custom_id_match = re.search(r'\{#([a-zA-Z][a-zA-Z0-9_-]*)\}', label)
        if custom_id_match:
            custom_id = custom_id_match.group(1)
            for i in range(idx + 1, len(tokens)):
                if tokens[i].type in ('heading_open', 'heading_close'):
                    break
                if tokens[i].type == 'inline':
                    tokens[i].content = re.sub(r'\s*\{#[^}]+\}\s*$', '', tokens[i].content).strip()
                    if tokens[i].children:
                        for j in range(len(tokens[i].children) - 1, -1, -1):
                            if tokens[i].children[j].type == 'text':
                                tokens[i].children[j].content = re.sub(r'\s*\{#[^}]+\}\s*$', '', tokens[i].children[j].content).rstrip()
                                break
                    break
        
        slug = custom_id if custom_id else slugify(label)
        
        if '_headings' not in env:
            env['_headings'] = []
        existing = [h for h in env['_headings'] if h['slug'] == slug]
        if existing:
            slug = f"{slug}-{len(existing)}"
        
        clean_label = re.sub(r'\s*\{#[^}]+\}\s*$', '', label).strip() if custom_id_match else label
        env['_headings'].append({'slug': slug, 'level': int(level), 'label': clean_label})
        
        return f'<h{level} id="{escapeHtml(slug)}">'

    md.renderer.rules['heading_open'] = heading_open_renderer

    env = {}
    result = md.render(text, env)
    
    if collect_headings:
        global _document_headings
        _document_headings = env.get('_headings', [])
    
    return result


_document_headings = []

# ---------------------------------------------------------------------------
# 阶段 4: 安全消毒
# ---------------------------------------------------------------------------

_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "a", "abbr", "b", "blockquote", "code", "em", "i", "img",
    "ins", "del", "s", "mark", "sub", "sup",
    "li", "ol", "ul", "pre", "small", "span", "strong",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    "div", "dl", "dt", "dd",
    "input", "label", "button",
    "details", "summary",
    "article", "section", "nav", "header", "footer", "main", "aside",
    "figure", "figcaption",
    "kbd", "samp", "var",
    "svg", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "g", "defs", "use", "symbol", "clippath", "mask", "lineargradient", "radialgradient",
    "stop", "pattern", "text", "tspan", "textpath", "foreignobject",
}

_ALLOWED_ATTRS = {
    "*": {"class", "style", "id", "dir", "title", "lang"},
    "a": {"href", "target", "rel", "download"},
    "img": {"src", "alt", "width", "height", "loading"},
    "input": {"type", "checked", "disabled", "placeholder"},
    "label": {"for"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align", "scope"},
    "col": {"span"},
    "details": {"open"},
    "ol": {"start", "type"},
    "svg": {"viewBox", "xmlns", "width", "height", "role", "aria-label", "fill", "stroke", "preserveAspectRatio"},
    "path": {"d", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "transform", "opacity", "clip-path"},
    "rect": {"x", "y", "width", "height", "rx", "ry", "fill", "stroke", "stroke-width", "transform", "opacity"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "transform", "opacity"},
    "ellipse": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width", "transform", "opacity"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "stroke-linecap", "transform", "opacity"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "stroke-linejoin", "transform", "opacity"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "stroke-linejoin", "transform", "opacity"},
    "g": {"transform", "fill", "stroke", "stroke-width", "opacity", "clip-path"},
    "defs": set(),
    "use": {"href", "xlink:href", "x", "y", "width", "height"},
    "text": {"x", "y", "dx", "dy", "fill", "font-family", "font-size", "font-weight", "text-anchor", "dominant-baseline", "transform", "opacity"},
    "tspan": {"x", "y", "dx", "dy", "fill", "font-family", "font-size", "font-weight"},
    "foreignobject": {"x", "y", "width", "height"},
}


def sanitize_html(html: str) -> str:
    import nh3
    import re as _re

    _style_blocks = []
    def _extract_style(m):
        _style_blocks.append(m.group(0))
        return f'<g class="mhs-sp-{len(_style_blocks) - 1}"></g>'

    html = _re.sub(r'<style[^>]*>.*?</style>', _extract_style, html, flags=_re.DOTALL)

    # Protect <pre> content to prevent nh3 from stripping leading whitespace
    _pre_blocks = []
    def _extract_pre(m):
        _pre_blocks.append(m.group(0))
        return f'<pre class="mhs-pre-prot-{len(_pre_blocks) - 1}"></pre>'
    
    html = _re.sub(r'<pre[^>]*>.*?</pre>', _extract_pre, html, flags=_re.DOTALL)

    result = nh3.clean(
        html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS,
        link_rel=None, clean_content_tags=set()
    )

    for i, block in enumerate(_style_blocks):
        result = result.replace(f'<g class="mhs-sp-{i}"></g>', block)

    # Restore protected <pre> blocks
    for i, block in enumerate(_pre_blocks):
        result = result.replace(f'<pre class="mhs-pre-prot-{i}"></pre>', block)

    return result

# ---------------------------------------------------------------------------
# 阶段 5 & 6: 模板注入 & 输出
# ---------------------------------------------------------------------------

def _load_text(path: Path) -> str:
    return _detect_and_read_file(path)


def load_template(name: str) -> str:
    tpl = _load_text(SKILL_ROOT / "references" / "templates" / f"{name}.html")
    if tpl:
        return tpl
    tpl = _load_text(SKILL_ROOT / "references" / "templates" / "default.html")
    if tpl:
        return tpl
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        "<style>{{css}}</style></head><body>"
        "<article class=\"nt-md2html-content\">{{content}}</article>"
        "</body></html>"
    )


def load_css(name: str) -> str:
    css = _load_text(SKILL_ROOT / "assets" / "themes" / f"{name}.css")
    if css:
        return css
    return _load_text(SKILL_ROOT / "assets" / "themes" / "default.css")


def _protect_code_blocks(text: str) -> tuple[str, list]:
    """保护代码块和内联代码内容，防止widget语法被解析
    
    使用深度计数正确处理嵌套代码块（如markdown代码块内包含bash/json代码块）。
    外层代码块会整体保护，内层代码块不会被单独提取。
    """
    import re
    code_blocks = []
    
    def escape_backticks_in_widgets(txt):
        widget_start_re = re.compile(r'^:{3,4}(\w[\w-]*)(?:\{[^\}]+\})?\s*$', re.MULTILINE)
        widget_end_re = re.compile(r'^:{3,4}\s*$', re.MULTILINE)
        
        result = []
        pos = 0
        
        while pos < len(txt):
            m = widget_start_re.search(txt, pos)
            if not m:
                result.append(txt[pos:])
                break
            
            result.append(txt[pos:m.start()])
            
            content_start = m.end()
            depth = 1
            search_pos = content_start
            
            while depth > 0 and search_pos < len(txt):
                next_open = widget_start_re.search(txt, search_pos)
                next_close = widget_end_re.search(txt, search_pos)
                
                if not next_close:
                    break
                
                if next_open and next_open.start() < next_close.start():
                    depth += 1
                    search_pos = next_open.end()
                else:
                    depth -= 1
                    if depth == 0:
                        widget_content = txt[content_start:next_close.start()]
                        widget_content = widget_content.replace('`', '\x00BACKTICK\x00')
                        result.append(txt[m.start():content_start] + widget_content + txt[next_close.start():next_close.end()])
                        pos = next_close.end()
                        break
                    search_pos = next_close.end()
            else:
                if depth > 0:
                    result.append(txt[m.start():])
                    break
            
            if depth > 0:
                result.append(txt[m.start():])
                break
        
        return ''.join(result)
    
    text = escape_backticks_in_widgets(text)
    
    def replace_fence_blocks(txt):
        result = []
        pos = 0
        fence_start_re = re.compile(r'^```(\w*)\s*$', re.MULTILINE)
        fence_end_re = re.compile(r'^```\s*$', re.MULTILINE)
        
        while pos < len(txt):
            m = fence_start_re.search(txt, pos)
            if not m:
                result.append(txt[pos:])
                break
            
            result.append(txt[pos:m.start()])
            
            lang = m.group(1)
            content_start = m.end()
            depth = 1
            search_pos = content_start
            
            while depth > 0 and search_pos < len(txt):
                next_open = fence_start_re.search(txt, search_pos)
                next_close = fence_end_re.search(txt, search_pos)
                
                if not next_close:
                    break
                
                if next_open and next_open.start() < next_close.start():
                    depth += 1
                    search_pos = next_open.end()
                else:
                    depth -= 1
                    if depth == 0:
                        content = txt[content_start:next_close.start()]
                        placeholder = f"MHSWITCH_FENCE_{len(code_blocks)}_"
                        code_blocks.append(('fence', placeholder, lang, content))
                        result.append(placeholder)
                        pos = next_close.end()
                        break
                    search_pos = next_close.end()
            else:
                if depth > 0:
                    result.append(txt[m.start():])
                    break
            
            if depth > 0:
                result.append(txt[m.start():])
                break
        
        return ''.join(result)
    
    protected = replace_fence_blocks(text)
    protected = protected.replace('\x00BACKTICK\x00', '`')

    double_inline_pattern = re.compile(r'``((?:[^`]|`(?!`))+?)``')
    
    def double_inline_replacer(m):
        content = m.group(1)
        placeholder = f"MHSWITCH_INLINE_{len(code_blocks)}_"
        code_blocks.append(('inline', placeholder, content))
        return placeholder
    
    protected = double_inline_pattern.sub(double_inline_replacer, protected)
    
    inline_code_pattern = re.compile(r'`([^`\n]+)`')
    
    def inline_replacer(m):
        content = m.group(1)
        placeholder = f"MHSWITCH_INLINE_{len(code_blocks)}_"
        code_blocks.append(('inline', placeholder, content))
        return placeholder
    
    protected = inline_code_pattern.sub(inline_replacer, protected)
    return protected, code_blocks


def _highlight_code(lang: str, content: str) -> str:
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
        from pygments.formatters import HtmlFormatter

        lexer = None
        if lang:
            if lang in ['javascript', 'js']:
                try:
                    from pygments.lexers.javascript import JavascriptLexer
                    lexer = JavascriptLexer(stripall=True)
                except Exception:
                    if _DEBUG_MODE:
                        import sys
                        import traceback
                        traceback.print_exc(file=sys.stderr)
                    try:
                        lexer = get_lexer_by_name('javascript', stripall=True)
                    except Exception:
                        if _DEBUG_MODE:
                            traceback.print_exc(file=sys.stderr)
            elif lang in ['typescript', 'ts']:
                try:
                    from pygments.lexers.javascript import TypeScriptLexer
                    lexer = TypeScriptLexer(stripall=True)
                except Exception:
                    if _DEBUG_MODE:
                        import sys
                        import traceback
                        traceback.print_exc(file=sys.stderr)
                    try:
                        lexer = get_lexer_by_name('typescript', stripall=True)
                    except Exception:
                        if _DEBUG_MODE:
                            traceback.print_exc(file=sys.stderr)
            else:
                try:
                    lexer = get_lexer_by_name(lang, stripall=True)
                except Exception:
                    if _DEBUG_MODE:
                        import sys
                        import traceback
                        traceback.print_exc(file=sys.stderr)
        if not lexer:
            try:
                lexer = guess_lexer(content)
            except Exception:
                if _DEBUG_MODE:
                    import traceback
                    traceback.print_exc(file=sys.stderr)
        if not lexer:
            lexer = TextLexer()

        private_fields = []
        import re
        def private_field_replacer(match):
            private_fields.append(match.group(0))
            return f"__PRIVATE_FIELD_{len(private_fields)-1}__"
        
        content_with_private = re.sub(r'#\b[a-zA-Z_]\w*', private_field_replacer, content)
        
        formatter = HtmlFormatter(
            nowrap=False,
            classprefix='mhs-hl-',
            cssclass='mhs-highlight',
            escape=False,
        )
        highlighted = highlight(content_with_private, lexer, formatter)
        
        for i, field in enumerate(private_fields):
            highlighted = highlighted.replace(f"__PRIVATE_FIELD_{i}__", field)
        
        if lang in ['javascript', 'js', 'typescript', 'ts']:
            highlighted = _post_process_js_highlighting(highlighted)
        
        return highlighted
    except ImportError:
        return None


def _post_process_js_highlighting(html: str) -> str:
    """后处理JavaScript代码高亮，识别函数调用并更新class"""
    import re
    
    common_methods = [
        'log', 'warn', 'error', 'info', 'debug',
        'parse', 'stringify',
        'then', 'catch', 'finally',
        'map', 'filter', 'reduce', 'forEach', 'find', 'some', 'every', 'includes', 'indexOf', 'push', 'pop', 'shift', 'unshift', 'slice', 'splice', 'concat', 'join', 'sort', 'reverse', 'fill', 'copyWithin',
        'abs', 'floor', 'ceil', 'round', 'max', 'min', 'sqrt', 'pow', 'random',
        'getTime', 'getDate', 'getMonth', 'getFullYear', 'getHours', 'getMinutes', 'getSeconds',
        'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        'querySelector', 'querySelectorAll', 'getElementById', 'getElementsByClassName', 'getElementsByTagName',
        'addEventListener', 'removeEventListener', 'dispatchEvent',
        'createElement', 'appendChild', 'removeChild', 'classList', 'style', 'setAttribute', 'getAttribute',
        'hasOwnProperty', 'prototype', 'constructor', 'call', 'apply', 'bind',
    ]
    
    for method in common_methods:
        pattern = rf'(<span class="[^"]*mhs-hl-nx[^"]*">)({re.escape(method)})(</span>)'
        replacement = rf'<span class="mhs-hl-func">{method}</span>'
        html = re.sub(pattern, replacement, html)
    
    dot_pattern = re.compile(r'<span class="[^"]*mhs-hl-nx[^"]*">([^<]+)\.</span><span class="[^"]*mhs-hl-nx[^"]*">([^<]+)</span>')
    html = dot_pattern.sub(r'<span class="mhs-hl-nx">\1.</span><span class="mhs-hl-func">\2</span>', html)
    
    pattern = r'(<span class="mhs-hl-kd">function</span><span class="mhs-hl-w"> </span>)(<span[^>]*>)(\w+)(</span>)'
    html = re.sub(pattern, r'\1<span class="mhs-hl-func">\3</span>', html)
    
    return html


def _restore_code_blocks_in_html(html: str, code_blocks: list) -> str:
    import re
    import html as html_module

    for item in code_blocks:
        if item[0] == 'fence':
            _, placeholder, lang, content = item

            highlighted = _highlight_code(lang, content)
            if highlighted:
                code_html = highlighted
            else:
                escaped = html_module.escape(content)
                lang_attr = f' class="language-{lang}"' if lang else ''
                code_html = f'<pre><code{lang_attr}>{escaped}</code></pre>'

            html = re.sub(rf'<h[1-6][^>]*>\s*{re.escape(placeholder)}\s*</h[1-6]>', code_html, html)
            html = re.sub(rf'<p>\s*{re.escape(placeholder)}\s*</p>', code_html, html)
            if placeholder in html and 'mhs-terminal' not in html[max(0, html.find(placeholder)-20):html.find(placeholder)]:
                html = html.replace(placeholder, code_html)
        elif item[0] == 'inline':
            _, placeholder, content = item
            escaped = html_module.escape(content)
            inline_html = f'<code>{escaped}</code>'
            html = html.replace(placeholder, inline_html)

    html = re.sub(r'<p>\s*(<pre><code[^>]*>)', r'\1', html)
    html = re.sub(r'(</code></pre>)\s*</p>', r'\1', html)
    return html


def _merge_widget_defs(
    base_defs: Dict[str, Any],
    custom_defs: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(base_defs)
    for name, definition in custom_defs.items():
        if not isinstance(definition, dict):
            continue
        required_keys = {"syntax", "template"}
        if not required_keys.issubset(definition.keys()):
            missing = required_keys - definition.keys()
            print(f"WARN: Custom widget '{name}' missing required keys: {missing}")
            continue
        merged[name] = {
            "description": definition.get("description", f"Custom widget: {name}"),
            "syntax": definition["syntax"],
            "template": definition["template"],
            "defaults": definition.get("defaults", {}),
        }
    return merged


def validate_widget_defs(widget_defs: Dict[str, Any]) -> tuple[bool, list[str]]:
    """验证 Widget 定义的语法正确性"""
    errors = []
    warnings = []
    
    if not isinstance(widget_defs, dict):
        errors.append("Widget definitions must be a dictionary")
        return False, errors
    
    for name, definition in widget_defs.items():
        if not isinstance(definition, dict):
            errors.append(f"Widget '{name}' definition must be a dictionary")
            continue
        
        required_keys = {"syntax", "template"}
        if not required_keys.issubset(definition.keys()):
            missing = required_keys - definition.keys()
            errors.append(f"Widget '{name}' missing required keys: {missing}")
        
        if "syntax" in definition:
            syntax = definition["syntax"]
            if syntax not in ["fence", "inline"]:
                errors.append(f"Widget '{name}' has invalid syntax type: '{syntax}'. Must be 'fence' or 'inline'")
        
        if "template" in definition:
            template = definition["template"]
            if not isinstance(template, str):
                errors.append(f"Widget '{name}' template must be a string")
        
        if "defaults" in definition:
            defaults = definition["defaults"]
            if not isinstance(defaults, dict):
                errors.append(f"Widget '{name}' defaults must be a dictionary")
            else:
                for key, value in defaults.items():
                    if not isinstance(value, (str, int, float, bool, type(None))):
                        warnings.append(f"Widget '{name}' default value for '{key}' is of type {type(value).__name__}, which may cause issues")
    
    all_messages = []
    if errors:
        all_messages.extend([f"ERROR: {e}" for e in errors])
    if warnings:
        all_messages.extend([f"WARN: {w}" for w in warnings])
    
    return len(errors) == 0, all_messages


def process(
    markdown: str,
    template: Optional[str] = None,
    widget_defs: Optional[Dict[str, Any]] = None,
    debug: bool = False,
    allow_eval: bool = False,
) -> str:
    global _document_headings, _widget_store, _DEBUG_MODE, _EVAL_ALLOWED
    _DEBUG_MODE = debug
    _EVAL_ALLOWED = allow_eval
    _document_headings = []

    if markdown.startswith('\ufeff'):
        markdown = markdown[1:]

    if len(markdown) > MAX_INPUT_SIZE:
        raise ValueError(f"输入内容过大 ({len(markdown)} bytes)，最大允许 {MAX_INPUT_SIZE} bytes")

    meta, body = parse_front_matter(markdown)
    tpl_name = meta.get("template") or template or "default"

    if widget_defs is None:
        widget_defs = load_widget_defs()

    custom_widgets = meta.get("widgets")
    if custom_widgets and isinstance(custom_widgets, dict):
        if debug:
            print(f"DEBUG: 发现 {len(custom_widgets)} 个自定义组件")
        widget_defs = _merge_widget_defs(widget_defs, custom_widgets)

    # Initialize widget store for this processing session
    _widget_store = []
    
    body, code_blocks = _protect_code_blocks(body)
    global _code_blocks_for_restore
    # 保存完整的信息：(type, placeholder, content, original_match)
    _code_blocks_for_restore = []
    for item in code_blocks:
        if item[0] == 'inline':
            # 内联代码需要保存原始的完整匹配信息
            _code_blocks_for_restore.append( (item[0], item[1], item[2], f"`{item[2]}`") )
        elif item[0] == 'fence':
            _code_blocks_for_restore.append( (item[0], item[1], item[3], item[3]) )
    
    # 第一步：展开所有 Widget (递归地，包含嵌套)
    body = expand_widgets(body, widget_defs, md_converter=lambda x: markdown_to_html(x, collect_headings=False))
    
    # 第二步：将剩余内容转换为 HTML
    terminal_pattern = re.compile(r'(<div class="mhs-terminal".*?</div>)', re.DOTALL)
    terminal_parts = terminal_pattern.split(body)
    processed_parts = []
    for part in terminal_parts:
        if terminal_pattern.match(part):
            processed_parts.append(part)
        else:
            processed_parts.append(markdown_to_html(part))
    html = ''.join(processed_parts)
    
    def fix_toc(html_text):
        import re
        toc_pattern = r'(<div class="mhs-toc"><div class="mhs-toc-title">)([^<]+)(</div>)([\s\S]*?)(</div>)'
        
        def replace_toc(m):
            title = m.group(2)
            if not _document_headings:
                return m.group(0)
            
            toc_items = []
            for h in _document_headings:
                indent = '  ' * (h['level'] - 1) if h['level'] > 1 else ''
                # 在生成 TOC 时，如果标题中含有 MHSWITCH_PH_，尝试先还原它们
                label_raw = h['label']
                label_restored = _restore_widgets(label_raw)
                
                # 再次清理还原后的 HTML 标签，只保留纯文本用于 TOC 展示（或保留简单标签）
                # 这里我们保留还原后的文字
                label_clean = re.sub(r'<[^>]+>', '', label_restored).strip()
                
                safe_slug = h['slug'].replace('"', '&quot;')
                safe_label = label_clean.replace('<', '&lt;').replace('>', '&gt;')
                toc_items.append(f'{indent}- [{safe_label}](#{safe_slug})')
            
            toc_md = '\n'.join(toc_items)
            from markdown_it import MarkdownIt
            md_toc = MarkdownIt()
            toc_html = md_toc.render(toc_md)
            
            return f'{m.group(1)}{title}{m.group(3)}{toc_html}{m.group(5)}'
        
        return re.sub(toc_pattern, replace_toc, html_text)
    
    html = fix_toc(html)

    # 第三步：强制恢复 Widget 占位符 (可能需要多次递归恢复，如果 Widget 模板里还有 PH)
    try:
        max_iter = 5
        while "MHSWITCH_PH_" in html and max_iter > 0:
            html = _restore_widgets(html)
            max_iter -= 1
    finally:
        _widget_store.clear()
    
    html = sanitize_html(html)

    # 清理空 <p> 标签（必须在 sanitize 之后，因为 nh3 会重新生成空 <p>）
    # MD 中 widget 前后/内部的空行被转换为 <p></p>，
    # 这些空标签会破坏 CSS Grid/Flex 布局（被当作 grid item 占据空间）
    html = re.sub(r'<p>\s*</p>', '', html)
    
    html = _restore_code_blocks_in_html(html, code_blocks)

    tpl_str = load_template(tpl_name)
    css_str = load_css(tpl_name)

    result = tpl_str.replace("{{content}}", html)
    result = result.replace("{{css}}", css_str)
    
    terminal_pattern = re.compile(r'<div class="mhs-terminal-body">.*?</div>', re.DOTALL)
    result = terminal_pattern.sub(lambda m: _restore_terminal_entities(m.group(0)), result)

    return result


_widget_store = []

def _restore_widgets(text: str) -> str:
    global _widget_store
    
    # 将占位符按照序号从大到小排序，防止 MHSWITCH_PH_1_ 匹配到 MHSWITCH_PH_10_ 的前缀
    # （虽然我们的占位符有尾随下划线，但逆序是更稳妥的做法）
    sorted_store = sorted(
        _widget_store,
        key=lambda x: int(re.search(r'\d+', x[0]).group()) if re.search(r'\d+', x[0]) else 0,
        reverse=True
    )
    
    # 递归还原：组件内可能包含其他组件的占位符
    max_passes = 10
    for pass_num in range(max_passes):
        changed = False
        for placeholder, html in sorted_store:
            if placeholder in text:
                text = text.replace(placeholder, html)
                changed = True
        if not changed:
            break
            
    return text

# ---------------------------------------------------------------------------
# 流式模式
# ---------------------------------------------------------------------------

def process_stream(
    template: Optional[str] = None,
    widget_defs: Optional[Dict[str, Any]] = None,
) -> None:
    import select

    buffer = ""
    last_output_len = 0

    while True:
        if sys.platform == "win32":
            line = sys.stdin.readline()
            if not line:
                break
        else:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not rlist:
                break
            line = sys.stdin.readline()
            if not line:
                break

        buffer += line

        if line.strip() == "" or buffer.rstrip().endswith("```"):
            result = process(buffer, template, widget_defs)

            if result:
                new_part = result[last_output_len:]
                if new_part:
                    sys.stdout.write(new_part)
                    sys.stdout.flush()
                last_output_len = len(result)

    if buffer.strip():
        result = process(buffer, template, widget_defs)
        new_part = result[last_output_len:]
        if new_part:
            sys.stdout.write(new_part)
            sys.stdout.flush()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="nt-md2html — Markdown 到 HTML 渲染器"
    )
    parser.add_argument("--markdown", type=str, help="需要转换的 Markdown 文本")
    parser.add_argument("--file", type=str, help="需要转换的 Markdown 文件路径")
    parser.add_argument("--output", type=str, help="输出 HTML 文件路径")
    parser.add_argument("--template", type=str, default=None, help="模板名称 (default / dark)")
    parser.add_argument("--stream", action="store_true", help="启用流式输入模式")
    parser.add_argument("--widget-defs", type=str, default=None, help="自定义 Widget 定义 JSON 路径")
    parser.add_argument("--validate-widgets", action="store_true", help="验证 Widget 定义的语法")
    parser.add_argument("--debug", action="store_true", help="启用调试模式，输出组件展开过程")
    parser.add_argument("--allow-eval", action="store_true", help="启用 eval 组件（默认禁用，存在安全风险）")
    
    # Subagent 委派相关参数
    parser.add_argument("--delegate", type=str, help="执行Subagent委派任务（传入委派消息或文件路径）")
    parser.add_argument("--suggest-workflow", choices=["has-file", "no-file", "has-content"], 
                        help="获取工作流建议")
    parser.add_argument("--check-subagent", action="store_true", 
                        help="检测Subagent是否可用")
    parser.add_argument("--validate-output", nargs="+", 
                        help="验证指定的输出文件")
    
    args = parser.parse_args()

    # Subagent 功能
    if args.delegate:
        if os.path.exists(args.delegate):
            delegate_msg = _detect_and_read_file(_resolve_safe_path(args.delegate))
        else:
            delegate_msg = args.delegate
        
        result = execute_delegated_task(delegate_msg)
        
        print(result.get("message", "No result message"))
        
        if not result.get("success"):
            sys.exit(1)
        return
    
    if args.suggest_workflow:
        has_file = args.suggest_workflow == "has-file"
        complexity = "medium" if args.suggest_workflow != "no-file" else "simple"
        suggestion = suggest_workflow(has_markdown_file=has_file, content_complexity=complexity)
        print(suggestion)
        return
    
    if args.check_subagent:
        available = detect_subagent_availability()
        print(f"Subagent可用: {'是' if available else '否'}")
        return
    
    if args.validate_output:
        validation_result = validate_output_files(args.validate_output)
        print(f"验证结果: {'通过' if validation_result['valid'] else '失败'}")
        for issue in validation_result.get('issues', []):
            print(f"  ⚠️ {issue}")
        return

    # 标准渲染流程
    wdefs = load_widget_defs(args.widget_defs) if args.widget_defs else None

    # Widget 验证功能
    if args.validate_widgets:
        if wdefs is None:
            wdefs = load_widget_defs()
        
        print("=" * 60)
        print("nt-md2html Widget 定义验证")
        print("=" * 60)
        print()
        
        # 验证组件定义
        valid, messages = validate_widget_defs(wdefs)
        
        # 按类型分组统计
        fence_widgets = sorted([name for name, defs in wdefs.items() if defs.get("syntax") == "fence"])
        inline_widgets = sorted([name for name, defs in wdefs.items() if defs.get("syntax") == "inline"])
        
        print(f"[组件总数] {len(wdefs)}")
        print()
        
        print(f"[围栏型组件] ({len(fence_widgets)}):")
        if fence_widgets:
            print("  " + ", ".join(fence_widgets))
        else:
            print("  (无)")
        print()
        
        print(f"[内联组件] ({len(inline_widgets)}):")
        if inline_widgets:
            print("  " + ", ".join(inline_widgets))
        else:
            print("  (无)")
        print()
        
        print("-" * 60)
        print("验证结果:")
        print("-" * 60)
        
        if messages:
            for msg in messages:
                if msg.startswith("ERROR:"):
                    print(f"  [X] {msg[7:]}")
                elif msg.startswith("WARN:"):
                    print(f"  [!] {msg[5:]}")
                else:
                    print(f"  {msg}")
        else:
            print("  [V] 所有组件定义均通过验证")
        
        print()
        print("=" * 60)
        print(f"最终结果: {'[V] 通过' if valid else '[X] 失败'}")
        print("=" * 60)
        
        if not valid:
            sys.exit(1)
        return

    # 调试模式 - 输出组件列表
    if args.debug and wdefs:
        print("=== 可用组件列表 ===")
        fence_widgets = [name for name, defs in wdefs.items() if defs.get("syntax") == "fence"]
        inline_widgets = [name for name, defs in wdefs.items() if defs.get("syntax") == "inline"]
        print(f"围栏型组件 ({len(fence_widgets)}): {', '.join(sorted(fence_widgets))}")
        print(f"内联组件 ({len(inline_widgets)}): {', '.join(sorted(inline_widgets))}")
        print()

    if args.markdown:
        result = process(args.markdown, args.template, wdefs, args.debug, args.allow_eval)
    elif args.file:
        text = _detect_and_read_file(Path(args.file))
        if not text:
            print(f"Error: Cannot read file {args.file}", file=sys.stderr)
            sys.exit(1)
        result = process(text, args.template, wdefs, args.debug, args.allow_eval)
    elif args.stream:
        process_stream(args.template, wdefs)
        return
    else:
        text = sys.stdin.read()
        result = process(text, args.template, wdefs, args.debug, args.allow_eval)

    if args.output:
        _smart_write_file(Path(args.output), result)
    else:
        print(result)


def validate_output_files(filepaths: list) -> dict:
    """验证输出文件的完整性"""
    result = {
        "valid": True,
        "files": [],
        "issues": []
    }
    
    for filepath in filepaths:
        file_info = {"path": filepath}
        
        if not os.path.exists(filepath):
            result["valid"] = False
            result["issues"].append(f"文件不存在: {filepath}")
            continue
        
        try:
            content = _detect_and_read_file(Path(filepath))
            
            file_info["size"] = len(content)
            file_info["type"] = "markdown" if filepath.endswith('.md') else "html"
            
            if not content.strip():
                result["issues"].append(f"文件为空: {filepath}")
            
            # HTML特定检查
            if filepath.endswith('.html'):
                if '<!DOCTYPE html>' not in content and '<html' not in content.lower():
                    result["issues"].append(f"HTML结构不完整: {filepath}")
                
                if 'mhs-' not in content:
                    result["issues"].append(f"未检测到nt-md2html组件: {filepath}")
            
            result["files"].append(file_info)
            
        except Exception as e:
            result["valid"] = False
            result["issues"].append(f"读取失败 {filepath}: {str(e)}")
    
    return result


if __name__ == "__main__":
    main()