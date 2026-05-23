#!/usr/bin/env python3
"""
nt-md2html Workflow Helper - 流程化工作流辅助工具

提供Subagent检测、任务委派、结果验证等功能。
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

SKILL_ROOT = Path(__file__).resolve().parent.parent


def detect_subagent() -> bool:
    """检测Subagent是否可用"""
    return os.environ.get('SUBAGENT_AVAILABLE', '').lower() in ('true', '1', 'yes')


def check_file_exists(filepath: str) -> bool:
    """检查文件是否存在"""
    return Path(filepath).exists()


def get_markdown_files(directory: str = ".") -> List[str]:
    """获取目录下所有Markdown文件"""
    path = Path(directory)
    return [str(f) for f in path.glob("*.md") if f.is_file()]


def validate_output(files: List[str]) -> Dict[str, Any]:
    """验证输出文件是否完整且有效"""
    result = {
        "valid": True,
        "files": [],
        "issues": []
    }
    
    for filepath in files:
        if not Path(filepath).exists():
            result["valid"] = False
            result["issues"].append(f"文件不存在: {filepath}")
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            result["issues"].append(f"文件为空: {filepath}")
        
        file_info = {
            "path": filepath,
            "size": len(content),
            "type": "markdown" if filepath.endswith('.md') else "html"
        }
        result["files"].append(file_info)
    
    return result


def create_delegate_message(task: str, input_data: str, theme: str = "default", 
                            output_path: str = None) -> str:
    """创建Subagent委派消息"""
    msg = f"""[MHSWITCH_DELEGATE]
task: {task}
input: {input_data}
theme: {theme}"""
    
    if output_path:
        msg += f"\noutput: {output_path}"
    
    msg += """
requirements:
  - 输出.md源文件（供AI阅读和编辑）
  - 输出.html最终文件（供人类阅读）"""
    
    return msg


def create_result_message(status: str, files: List[str], issues: List[str] = None) -> str:
    """创建结果回传消息"""
    msg = f"""[MHSWITCH_RESULT]
status: {status}
files:"""
    
    for f in files:
        msg += f"\n  - path: {f}"
    
    msg += "\n]"
    
    if issues:
        msg += "\nissues:"
        for issue in issues:
            msg += f"\n  - {issue}"
    else:
        msg += "\nissues: []"
    
    return msg


def suggest_workflow(has_file: bool, has_content: bool, subagent_available: bool) -> str:
    """根据当前状态建议最佳工作流"""
    if has_file:
        if subagent_available:
            return """建议流程：委托Subagent执行

步骤：
1. 检测到Markdown文件，准备渲染
2. 创建委派消息给Subagent
3. Subagent执行：python scripts/render.py --file <file> --output <output.html>"""
        else:
            return """建议流程：主Agent直接执行

步骤：
1. 渲染：python scripts/render.py --file <input.md> --output <output.html>

输出：
- input.md (源文件，已存在)
- output.html (新生成)"""
    
    elif has_content:
        if subagent_available:
            return """建议流程：生成MD后委托渲染

步骤：
1. 将用户需求转换为优化的Markdown格式
2. 保存为临时.md文件
3. 委托Subagent执行渲染"""
        else:
            return """建议流程：主Agent全流程处理

步骤：
1. 根据用户需求生成Markdown内容
2. 保存为output.md
3. 渲染：python scripts/render.py --file output.md --output output.html"""
    
    else:
        return """需要更多信息

请确认：
- 是否有现成的Markdown文件？
- 需要生成什么类型的内容？
- 偏好的主题样式？"""


def main():
    parser = argparse.ArgumentParser(description="nt-md2html Workflow Helper")
    parser.add_argument("--check-file", help="检查指定文件是否存在")
    parser.add_argument("--list-md", help="列出目录下的Markdown文件", action="store_true")
    parser.add_argument("--detect-subagent", help="检测Subagent是否可用", action="store_true")
    parser.add_argument("--validate", nargs="+", help="验证指定的输出文件")
    parser.add_argument("--suggest", help="获取工作流建议", choices=["has-file", "no-file", "has-content"])
    parser.add_argument("--create-delegate", help="创建委派消息", nargs=3, 
                        metavar=("TASK", "INPUT", "THEME"))
    
    args = parser.parse_args()
    
    if args.check_file:
        exists = check_file_exists(args.check_file)
        print(f"文件检查: {args.check_file} - {'存在' if exists else '不存在'}")
    
    elif args.list_md:
        files = get_markdown_files()
        print(f"找到 {len(files)} 个Markdown文件:")
        for f in files:
            print(f"  - {f}")
    
    elif args.detect_subagent:
        available = detect_subagent()
        print(f"Subagent检测: {'可用' if available else '不可用'}")
    
    elif args.validate:
        result = validate_output(args.validate)
        print(f"验证结果: {'通过' if result['valid'] else '失败'}")
        print(f"文件数: {len(result['files'])}")
        if result['issues']:
            print("问题:")
            for issue in result['issues']:
                print(f"  ⚠️  {issue}")
    
    elif args.suggest:
        subagent = detect_subagent()
        
        suggestions = {
            "has-file": suggest_workflow(True, False, subagent),
            "no-file": suggest_workflow(False, False, subagent),
            "has-content": suggest_workflow(False, True, subagent)
        }
        
        print(suggestions[args.suggest])
        print(f"\n(Subagent状态: {'可用' if subagent else '不可用'})")
    
    elif args.create_delegate:
        task, input_data, theme = args.create_delegate
        msg = create_delegate_message(task, input_data, theme)
        print("=== 委派消息 ===")
        print(msg)
    
    else:
        # 默认显示状态信息
        print("nt-md2html Workflow Helper")
        print("=" * 40)
        print(f"Subagent可用: {'是' if detect_subagent() else '否'}")
        
        md_files = get_markdown_files()
        print(f"当前目录MD文件数: {len(md_files)}")
        if md_files:
            print("文件列表:")
            for f in md_files[:5]:
                print(f"  📄 {f}")


if __name__ == "__main__":
    main()
