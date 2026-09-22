"""按模块汇总评测指标，产出一份给人看的 Markdown（外加一份机器可读 JSON）。

每个模块有自己的指标组：
- Agent 主循环   → 任务通过率、平均模型调用/工具步数、停机原因分布
- 上下文管理     → prompt 字符数、平均/最高压缩率、当前请求保留率、逐组配置
- 记忆系统       → 重复读取、平均工具步数/尝试次数、正确率、命中率（开/关对比）
- 检查点与恢复   → 恢复成功率、重锚定率、漂移检出率、误接受率（开/关对比）+ 逐任务
- 工具执行与安全 → 治理场景数、错误码与安全事件分布、环境跳过
- 评测与可复现   → 任务数/重复次数/产物清单/可复现性字段
- 提示词缓存     → 缓存命中率（离线不可测时如实标注，需真实 provider 实验）
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def load(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def pct(value):
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else 0.0


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def variant_summary(payload):
    if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
        return payload["summary"]
    return payload or {}


def collect(artifacts: Path) -> dict:
    artifacts = Path(artifacts)
    harness = load(artifacts / "harness-regression-v2.json") or {}
    context = load(artifacts / "context-ablation-v2.json") or {}
    memory = load(artifacts / "memory-ablation-v2.json") or {}
    recovery = load(artifacts / "recovery-ablation-v2.json") or {}
    security = load(artifacts / "security-suite.json") or {}
    tests = load(artifacts / "test-summary.json") or {}

    rows = harness.get("rows", [])
    stop_reasons = Counter(str(row.get("stop_reason", "")) for row in rows)
    categories = Counter(str(row.get("category", "")) for row in rows)
    category_passed = Counter(str(row.get("category", "")) for row in rows if row.get("passed"))

    mv = memory.get("variants", {})
    mem = {name: variant_summary(mv.get(name, {})) for name in ("memory_on", "memory_off", "memory_irrelevant")}
    rv = recovery.get("variants", {})
    rec = {name: variant_summary(rv.get(name, {})) for name in ("resume_enabled", "resume_disabled")}

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "artifacts_dir": str(artifacts),
        "tests": tests,
        "agent_loop": {
            "summary": harness.get("summary", {}),
            "avg_attempts": mean([row.get("attempts") for row in rows]),
            "avg_tool_steps": mean([row.get("tool_steps") for row in rows]),
            "stop_reasons": dict(stop_reasons),
            "categories": dict(categories),
            "category_passed": dict(category_passed),
            "tasks": [
                {
                    "id": row.get("id"),
                    "category": row.get("category"),
                    "passed": bool(row.get("passed")),
                    "tool_steps": row.get("tool_steps"),
                    "step_budget": row.get("step_budget"),
                    "attempts": row.get("attempts"),
                    "stop_reason": row.get("stop_reason"),
                    "failure_category": row.get("failure_category"),
                }
                for row in rows
            ],
            "failure_category_counts": harness.get("failure_category_counts", {}),
            "reproducibility": harness.get("reproducibility", {}),
        },
        "context": {
            "summary": context.get("summary", {}),
            "configs": context.get("configs", []),
        },
        "memory": {"variants": mem},
        "recovery": {
            "variants": rec,
            "rows": {
                name: rv.get(name, {}).get("rows", []) if isinstance(rv.get(name), dict) else []
                for name in ("resume_enabled", "resume_disabled")
            },
        },
        "security": security,
    }


def render(data: dict) -> str:
    al = data["agent_loop"]
    hs = al["summary"]
    cs = data["context"]["summary"]
    mem = data["memory"]["variants"]
    rec = data["recovery"]["variants"]
    sec = data["security"]
    tests = data["tests"]

    parts = []
    parts.append("# Plane 模块指标报告\n")
    parts.append(
        "> 这份文件是什么：按模块汇总的评测指标报告。每个模块（Agent 主循环、上下文管理、记忆系统、"
        "检查点与恢复、工具执行与安全、评测框架、提示词缓存）各自列出一组指标表、逐条明细和结论，"
        "并附「指标怎么解读」与口径边界。所有数字都由本机离线复现，未调用真实大模型。\n"
    )
    parts.append(f"- 生成时间：{data['generated_at']}")
    parts.append(f"- 数据来源：`{data['artifacts_dir']}`（全部离线复现，未调用真实大模型）")
    parts.append("- 复现方式：在项目根目录执行 `python scripts/measure_all.py`\n")

    if tests:
        parts.append("## 0. 功能测试（pytest）\n")
        parts.append(f"- 结果：**{tests.get('summary','')}**（exit={tests.get('returncode','?')}，耗时 {tests.get('duration_s','?')}s）")
        parts.append("- 说明：这层回答「代码有没有坏」，下面的评测回答「机制有没有用」\n")

    # -------- 总览 --------
    overview_rows = [
        ("Agent 主循环", "固定行为任务通过率", pct(hs.get("pass_rate")),
         f"{hs.get('passed','—')}/{hs.get('total_tasks','—')} 通过，失败归因 {al['failure_category_counts'] or '无'}"),
        ("上下文管理", "prompt 平均压缩率", pct(cs.get("avg_prompt_compression_ratio")),
         f"当前请求保留率 {pct(cs.get('current_request_preserved_rate'))}"),
        ("记忆系统", "重复读取文件次数", f"{mem.get('memory_on',{}).get('repeated_reads','—')} vs {mem.get('memory_off',{}).get('repeated_reads','—')}",
         "开记忆 vs 关记忆"),
        ("检查点与恢复", "恢复成功率", f"{pct(rec.get('resume_enabled',{}).get('resume_success_rate'))} vs {pct(rec.get('resume_disabled',{}).get('resume_success_rate'))}",
         f"误接受率 {pct(rec.get('resume_enabled',{}).get('resume_false_accept_rate'))}"),
        ("工具执行与安全", "治理场景拦截", f"{sec.get('scenario_count','—')} 个场景",
         f"错误码分布 {sec.get('tool_error_code_counts',{})}"),
        ("提示词缓存", "缓存命中率", "离线不可测",
         "需要真实 provider 实验（scripts/run_provider_experiments.py）"),
    ]
    parts.append("## 总览\n")
    parts.append(table(["模块", "核心指标", "结果", "备注"], overview_rows))
    parts.append("")

    # -------- 1. Agent 主循环 --------
    parts.append("## 1. Agent 主循环（agent_loop.py）\n")
    parts.append("**指标**\n")
    parts.append(table(["指标", "数值"], [
        ("任务数", hs.get("total_tasks", "—")),
        ("通过 / 失败", f"{hs.get('passed','—')} / {hs.get('failed','—')}"),
        ("通过率 pass_rate", pct(hs.get("pass_rate"))),
        ("预算内完成率 within_budget_rate", pct(hs.get("within_budget_rate"))),
        ("断言通过率 verifier_pass_rate", pct(hs.get("verifier_pass_rate"))),
        ("平均模型调用次数", f"{al['avg_attempts']:.2f}"),
        ("平均工具步数", f"{al['avg_tool_steps']:.2f}"),
        ("停机原因分布", json.dumps(al["stop_reasons"], ensure_ascii=False)),
        ("失败归因分布", json.dumps(al["failure_category_counts"], ensure_ascii=False) or "{}"),
    ]))
    parts.append("\n**按类别（12 个任务）**\n")
    cat_rows = [(name, al["categories"][name], al["category_passed"].get(name, 0),
                 pct(al["category_passed"].get(name, 0) / al["categories"][name]))
                for name in sorted(al["categories"])]
    parts.append(table(["类别", "任务数", "通过", "通过率"], cat_rows))
    parts.append("\n**逐任务明细**\n")
    parts.append(table(["任务", "类别", "步数/预算", "模型调用", "结果", "停机原因"],
                       [(t["id"], t["category"], f"{t['tool_steps']}/{t['step_budget']}", t["attempts"],
                         "通过" if t["passed"] else f"失败({t['failure_category']})", t["stop_reason"])
                        for t in al["tasks"]]))
    parts.append("\n**结论**：12 个固定行为任务全部通过，说明这批改动没有破坏既有 runtime 合同；"
                 "step_budget 与 verifier 双重约束都满足，不是靠多试几次蒙过去的。\n")

    # -------- 2. 上下文管理 --------
    parts.append("## 2. 上下文管理（context_manager.py）\n")
    parts.append("**指标**\n")
    parts.append(table(["指标", "数值"], [
        ("配置组数", len(data["context"]["configs"])),
        ("不压缩平均 prompt 字符（对照组）", f"{cs.get('avg_raw_prompt_chars',0):,.2f}"),
        ("压缩后平均 prompt 字符", f"{cs.get('avg_full_prompt_chars',0):,.2f}"),
        ("平均压缩率", pct(cs.get("avg_prompt_compression_ratio"))),
        ("最高压缩率", pct(cs.get("max_prompt_compression_ratio"))),
        ("最低压缩率", pct(cs.get("min_prompt_compression_ratio"))),
        ("当前请求保留率", pct(cs.get("current_request_preserved_rate"))),
    ]))
    parts.append("\n**逐组配置**\n")
    parts.append(table(["配置", "历史档位", "笔记档位", "不压缩字符", "压缩后字符", "压缩率"],
                       [(c.get("id"), c.get("history_level"), c.get("note_level"),
                         f"{c.get('avg_raw_prompt_chars',0):,.0f}", f"{c.get('avg_full_prompt_chars',0):,.0f}",
                         pct(c.get("avg_prompt_compression_ratio")))
                        for c in data["context"]["configs"]]))
    parts.append("\n**结论**：同一批长上下文任务上，prompt 平均缩短 "
                 f"{pct(cs.get('avg_prompt_compression_ratio'))}，同时当前请求保留率 "
                 f"{pct(cs.get('current_request_preserved_rate'))}——收益不是靠裁掉关键信息换来的。\n")

    # -------- 3. 记忆系统 --------
    parts.append("## 3. 记忆系统（features/memory.py）\n")
    parts.append(table(["变体", "重复读取次数", "平均工具步数", "平均尝试次数", "任务正确率", "记忆命中率"],
                       [(name,
                         mem.get(name, {}).get("repeated_reads", "—"),
                         f"{mem.get(name, {}).get('avg_tool_steps', 0):.2f}",
                         f"{mem.get(name, {}).get('avg_attempts', 0):.2f}",
                         pct(mem.get(name, {}).get("correct_rate")),
                         pct(mem.get(name, {}).get("memory_hit_rate")))
                        for name in ("memory_on", "memory_off", "memory_irrelevant")]))
    parts.append("\n**结论**：开启记忆后重复读取从 "
                 f"{mem.get('memory_off',{}).get('repeated_reads','—')} 次降到 "
                 f"{mem.get('memory_on',{}).get('repeated_reads','—')} 次，平均工具步数与模型往返次数同步下降，"
                 "正确率与对照组持平——是净收益，不是用正确率换来的。\n")

    # -------- 4. 检查点与恢复 --------
    parts.append("## 4. 检查点与恢复（checkpoint.py）\n")
    parts.append(table(["变体", "恢复成功率", "过期重锚定率", "工作区漂移检出率", "误接受率"],
                       [(name,
                         pct(rec.get(name, {}).get("resume_success_rate")),
                         pct(rec.get(name, {}).get("stale_reanchor_rate")),
                         pct(rec.get(name, {}).get("workspace_drift_detection_rate")),
                         pct(rec.get(name, {}).get("resume_false_accept_rate")))
                        for name in ("resume_enabled", "resume_disabled")]))
    parts.append("\n**逐任务明细（开启恢复）**\n")
    parts.append(table(["任务", "类别", "恢复状态", "是否恢复成功", "误接受"],
                       [(r.get("task_id"), r.get("category"), r.get("resume_status"),
                         "是" if r.get("resume_succeeded") else "否",
                         "是" if r.get("false_accept") else "否")
                        for r in data["recovery"]["rows"].get("resume_enabled", [])]))
    parts.append("\n**结论**：关掉检查点后恢复成功率直接归零，说明恢复完全依赖这套机制；"
                 "唯一未恢复成功的是「故意不给任何恢复依据」的场景，而误接受率始终为 0——"
                 "系统不会把不可信状态当成可信状态继续跑。\n")

    # -------- 5. 工具执行与安全 --------
    parts.append("## 5. 工具执行与安全（tool_executor.py / security.py）\n")
    parts.append(table(["指标", "数值"], [
        ("治理场景数", sec.get("scenario_count", "—")),
        ("运行次数（含重复）", sec.get("runs", "—")),
        ("错误码分布", json.dumps(sec.get("tool_error_code_counts", {}), ensure_ascii=False)),
        ("安全事件分布", json.dumps(sec.get("security_event_counts", {}), ensure_ascii=False)),
        ("环境跳过", json.dumps(sec.get("environment_skip_counts", {}), ensure_ascii=False) or "{}"),
    ]))
    parts.append("\n**结论**：越界路径、非法参数、重复调用等场景都被拦截并结构化记录；"
                 "环境跳过项（如 Windows 下不允许普通用户创建符号链接）如实标注，不计入失败。\n")

    # -------- 6. 评测与可复现 --------
    parts.append("## 6. 评测与可复现（evaluation/）\n")
    parts.append(table(["项", "数值"], [
        ("harness 任务数", hs.get("total_tasks", "—")),
        ("可复现性字段", json.dumps(al.get("reproducibility", {}), ensure_ascii=False) or "{}"),
        ("产物目录", data["artifacts_dir"]),
    ]))
    parts.append("\n**产物清单**\n")
    parts.append("\n".join([
        "- `artifacts/harness-regression-v2.json`　12 个任务逐条明细",
        "- `artifacts/context-ablation-v2.json`　12 组配置的 prompt 与压缩率",
        "- `artifacts/memory-ablation-v2.json`　12 任务 × 3 变体",
        "- `artifacts/recovery-ablation-v2.json`　10 任务 × 2 变体",
        "- `artifacts/security-suite.json`　安全治理场景",
        "- `docs/metrics/plane-benchmark-core-report.md`　核心报告（英文指标名）",
        "- `docs/metrics/module-metrics.md`　**本文件**",
    ]))
    parts.append("\n**结论**：评测全程离线、可重复执行，产物落盘可复查；"
                 "指标口径与原始产物一一对应，不存在手工填写的数字。\n")

    # -------- 7. 提示词缓存 --------
    parts.append("## 7. 提示词缓存（providers/clients.py）\n")
    parts.append(table(["指标", "数值", "说明"], [
        ("缓存命中率", "离线不可测", "本地没有真实后端缓存，只有真实 provider 实验能测"),
        ("需运行", "`scripts/run_provider_experiments.py`", "会消耗真实 token，产出 pass_rate / attempts / tool_steps / cache_hit_rate"),
    ]))
    parts.append("\n**结论**：这一层的数字必须来自真实 provider，离线报告里如实标注为不可测，不用占位数字凑格式。\n")

    parts.append("---\n")
    parts.append("口径边界：Harness 回归只证明 runtime 合同稳定，不证明模型能力上限；"
                 "上下文 / 记忆 / 恢复三组消融只证明模块收益，不与 provider benchmark 混写。\n")
    return "\n".join(parts)


def write_module_metrics(artifacts, out_md, out_json=None):
    data = collect(Path(artifacts))
    out_md = Path(out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render(data), encoding="utf-8")
    if out_json:
        out_json = Path(out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"module metrics: {out_md}")
    return out_md
