"""给评测产物加上"这份文件是什么"的开头说明。

JSON 不支持注释，所以在每个文件最前面插入一个 `_readme` 字段（标准 JSON 合法），
打开文件第一眼就能看到：这份文件属于哪个模块、体现什么、关键字段怎么看、怎么复现。
Markdown 报告则在标题下方插入一段引用块说明。
"""

import json
from pathlib import Path

REPRODUCE = "python scripts/measure_all.py"

HEADERS = {
    "test-summary.json": {
        "what": "功能测试（pytest）结果，回答「代码有没有坏」。",
        "module": "全部模块（tests/）",
        "key_fields": "summary 是 pytest 汇总行（通过 / 跳过数量）；returncode=0 表示全部通过；duration_s 是耗时。",
        "reproduce": "python -m pytest tests -q",
    },
    "harness-regression-v2.json": {
        "what": "12 个固定行为任务的逐条结果：文档改写、精确替换、越界与非法调用后的恢复、检查点与恢复契约、长期记忆契约。",
        "module": "Agent 主循环 / 工具执行 / 检查点（agent_loop.py、tool_executor.py、checkpoint.py）",
        "key_fields": "summary.pass_rate 是整体通过率；rows[] 每条含 passed、tool_steps/step_budget、verifier_passed、within_budget、failure_category。",
        "reproduce": REPRODUCE,
    },
    "context-ablation-v2.json": {
        "what": "12 组长上下文配置下，prompt 在「不压缩（对照组）」与「启用压缩」两种情况的长度对比，用来量化上下文管理的收益。",
        "module": "上下文管理（context_manager.py）",
        "key_fields": "summary.avg_raw_prompt_chars 是对照组字符数、avg_full_prompt_chars 是压缩后；avg/max_prompt_compression_ratio 是压缩率；current_request_preserved_rate 是安全边界（当前请求是否始终保住）。configs[] 是逐组明细。",
        "reproduce": REPRODUCE,
    },
    "memory-ablation-v2.json": {
        "what": "12 个记忆依赖任务在三种变体（开记忆 / 关记忆 / 无关记忆）下的重复读取、工具步数与正确率对比。",
        "module": "记忆系统（features/memory.py）",
        "key_fields": "variants.memory_on 与 variants.memory_off 对比 repeated_reads、avg_tool_steps、avg_attempts、correct_rate、memory_hit_rate；正确率持平才说明是净收益。",
        "reproduce": REPRODUCE,
    },
    "recovery-ablation-v2.json": {
        "what": "10 个恢复任务在「开启检查点 / 关闭检查点」两种情况下的恢复能力对比，覆盖基础恢复、部分状态过期、工作区漂移、结构不兼容、工具半成功五类场景。",
        "module": "检查点与恢复（checkpoint.py、runtime.py）",
        "key_fields": "variants.resume_enabled.summary 含 resume_success_rate（恢复成功率）、stale_reanchor_rate（过期重锚定率）、workspace_drift_detection_rate（漂移检出率）、resume_false_accept_rate（误接受率，越低越安全）；rows 是逐任务明细。",
        "reproduce": REPRODUCE,
    },
    "security-suite.json": {
        "what": "10 个安全治理场景的拦截结果：越界路径、非法参数、高风险审批拒绝、只读阻断、重复调用等。",
        "module": "工具执行与安全（tool_executor.py、security.py）",
        "key_fields": "tool_error_code_counts / security_event_counts 是各类拦截分布；environment_skip_counts 是环境性跳过（例如 Windows 下普通用户不能建符号链接），不计入失败；rows[] 是逐场景明细。",
        "reproduce": REPRODUCE,
    },
    "module-metrics.json": {
        "what": "docs/metrics/module-metrics.md 的机器可读版本：按模块汇总的全部指标。",
        "module": "评测框架（evaluation/）",
        "key_fields": "agent_loop / context / memory / recovery / security 五个键分别对应各模块指标；tests 是 pytest 汇总。",
        "reproduce": REPRODUCE,
    },
}

MARKDOWN_NOTES = {
    "module-metrics.md": (
        "这份文件是什么：按模块汇总的评测指标报告。每个模块（Agent 主循环、上下文管理、记忆系统、"
        "检查点与恢复、工具执行与安全、评测框架、提示词缓存）各自列出一组指标表、逐条明细和结论，"
        "并附「指标怎么解读」与口径边界。所有数字都由本机离线复现，未调用真实大模型。"
    ),
    "plane-benchmark-core-report.md": (
        "这份文件是什么：四组离线评测（Harness 回归 / 上下文消融 / 记忆消融 / 恢复消融）的指标汇总，"
        "用来回答「这些机制到底有没有用」。逐条明细见同目录 module-metrics.md 与 artifacts/ 下的 JSON。"
    ),
}


def annotate(path) -> bool:
    """给单个 JSON 产物插入 _readme 字段（已存在则跳过），返回是否写入。"""
    path = Path(path)
    if not path.is_file():
        return False
    header = HEADERS.get(path.name)
    if not header:
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "_readme" in payload:
        return False
    annotated = {
        "_readme": {
            "file": path.name,
            "what": header["what"],
            "module": header["module"],
            "key_fields": header["key_fields"],
            "reproduce": header["reproduce"],
            "note": "本字段仅用于说明文件用途，不参与任何指标计算。",
        },
        **(payload if isinstance(payload, dict) else {"payload": payload}),
    }
    path.write_text(json.dumps(annotated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def annotate_all(directory) -> list:
    """给目录下所有已知产物补说明，返回被写入的文件名列表。"""
    directory = Path(directory)
    written = []
    for name in HEADERS:
        if annotate(directory / name):
            written.append(name)
    return written


def annotate_markdown(path) -> bool:
    """在 Markdown 报告标题下方插入一段说明引用块（已存在则跳过）。"""
    path = Path(path)
    note = MARKDOWN_NOTES.get(path.name)
    if not note or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if note in text or "这份文件是什么" in text:
        return False
    lines = text.splitlines()
    if not lines or not lines[0].startswith("#"):
        return False
    block = ["", f"> {note}", ""]
    if len(lines) > 1 and lines[1].strip() == "":
        lines = [lines[0]] + block + lines[2:]
    else:
        lines = [lines[0]] + block + lines[1:]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts")
    names = annotate_all(target)
    md = [p for p in (Path("docs") / "metrics").glob("*.md") if annotate_markdown(p)]
    print("已加说明的 JSON:", names)
    print("已加说明的 Markdown:", [p.name for p in md])
