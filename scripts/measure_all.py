#!/usr/bin/env python3
"""一键跑出 plane 的离线评价指标，并按模块生成报告。

用法（在项目里任意位置执行都行）：
    python scripts/measure_all.py                                  # 完整：pytest + 4 组评测 + 安全套件
    python scripts/measure_all.py --skip-tests --repetitions 1     # 快速版（约 1 分钟）

产物：
    artifacts/*.json                             原始产物（.gitignore 已忽略）
    docs/metrics/plane-benchmark-core-report.md  核心报告
    docs/metrics/module-metrics.md               按模块组织的指标报告

全过程不调用真实大模型，可离线复现；判定口径 = 断言通过 + 步数预算内 + 不越界。
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
for entry in (str(SCRIPTS), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from module_metrics import write_module_metrics  # noqa: E402
from artifact_headers import annotate, annotate_all, annotate_markdown  # noqa: E402
from plane.evaluation.evaluator import run_harness_regression_v2  # noqa: E402
from plane.evaluation.metrics import (  # noqa: E402
    run_context_ablation_v2,
    run_memory_ablation_v2,
    run_recovery_ablation_v2,
    run_security_experiment_suite,
    write_benchmark_core_report,
)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="跑出 plane 的全部离线评价指标。")
    parser.add_argument("--repo", default=str(ROOT), help="项目根目录（默认脚本所在仓库）")
    parser.add_argument("--out-dir", default=None, help="产物目录，默认 <repo>/artifacts")
    parser.add_argument("--report", default=None, help="核心报告路径，默认 <repo>/docs/metrics/plane-benchmark-core-report.md")
    parser.add_argument("--module-report", default=None, help="模块指标报告路径，默认 <repo>/docs/metrics/module-metrics.md")
    parser.add_argument("--repetitions", type=int, default=3, help="消融实验重复次数（越大越稳、越慢）")
    parser.add_argument("--skip-tests", action="store_true", help="跳过 pytest")
    return parser


def run_pytest(repo):
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return {
        "returncode": proc.returncode,
        "summary": lines[-1] if lines else "(no output)",
        "duration_s": round(time.monotonic() - started, 1),
    }


def pct(value):
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def variant_summary(payload):
    """记忆消融的 variants 是扁平指标字典，恢复消融是 {"summary": ..., "rows": [...]}。"""
    if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
        return payload["summary"]
    return payload


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else repo / "artifacts"
    metrics_dir = repo / "docs" / "metrics"
    report_path = Path(args.report) if args.report else metrics_dir / "plane-benchmark-core-report.md"
    module_md = Path(args.module_report) if args.module_report else metrics_dir / "module-metrics.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    benchmark = (repo / "benchmarks" / "coding_tasks.json").resolve()

    print(f"仓库: {repo}")
    print(f"基准: {benchmark}")
    print(f"产物: {out_dir}")
    print()

    if not args.skip_tests:
        print("== 1. 功能测试（pytest）==")
        tests = run_pytest(repo)
        (out_dir / "test-summary.json").write_text(
            json.dumps(tests, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        annotate(out_dir / "test-summary.json")
        print(f"   {tests['summary']}   （{tests['duration_s']}s, exit={tests['returncode']}）")
        print()

    print("== 2. harness 回归（12 个固定行为任务）==")
    harness_path = out_dir / "harness-regression-v2.json"
    harness = run_harness_regression_v2(benchmark_path=benchmark, artifact_path=harness_path)
    annotate(harness_path)
    hs = harness["summary"]
    print(f"   任务 {hs['total_tasks']} 个 / 通过 {hs['passed']} 个 → pass_rate={pct(hs['pass_rate'])}")
    print(f"   预算内 {hs['within_budget']} / 断言通过 {hs['verifier_passes']} / 失败归因 {hs['failure_category_counts']}")
    print()

    print("== 3. 上下文消融（12 组配置，看 prompt 压缩率）==")
    context_path = out_dir / "context-ablation-v2.json"
    context = run_context_ablation_v2(artifact_path=context_path, repetitions=args.repetitions)
    annotate(context_path)
    cs = context["summary"]
    print(f"   不压缩平均 {cs['avg_raw_prompt_chars']:.1f} 字符 → 压缩后 {cs['avg_full_prompt_chars']:.1f} 字符")
    print(f"   平均压缩率 {pct(cs['avg_prompt_compression_ratio'])} / 最高 {pct(cs['max_prompt_compression_ratio'])}")
    print(f"   当前请求保留率 {pct(cs['current_request_preserved_rate'])}")
    print()

    print("== 4. 记忆消融（12 个任务，开/关记忆对比）==")
    memory_path = out_dir / "memory-ablation-v2.json"
    memory = run_memory_ablation_v2(artifact_path=memory_path, repetitions=args.repetitions)
    annotate(memory_path)
    for variant, payload in memory["variants"].items():
        vs = variant_summary(payload)
        print(
            f"   {variant:<18} 重复读取 {vs['repeated_reads']:>3} 次 | 平均工具步数 {vs['avg_tool_steps']:.2f} "
            f"| 平均尝试 {vs['avg_attempts']:.2f} | 正确率 {pct(vs['correct_rate'])}"
        )
    print()

    print("== 5. 恢复消融（10 个任务，开/关恢复对比）==")
    recovery_path = out_dir / "recovery-ablation-v2.json"
    recovery = run_recovery_ablation_v2(artifact_path=recovery_path, repetitions=args.repetitions)
    annotate(recovery_path)
    for variant, payload in recovery["variants"].items():
        vs = variant_summary(payload)
        print(
            f"   {variant:<16} 恢复成功率 {pct(vs['resume_success_rate'])} | 过期重锚定 {pct(vs['stale_reanchor_rate'])} "
            f"| 漂移检出 {pct(vs['workspace_drift_detection_rate'])} | 误接受 {pct(vs['resume_false_accept_rate'])}"
        )
    print()

    print("== 6. 安全治理场景（越界 / 非法参数 / 重复调用拦截）==")
    security = run_security_experiment_suite(repetitions=args.repetitions)
    (out_dir / "security-suite.json").write_text(
        json.dumps(security, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    annotate(out_dir / "security-suite.json")
    print(f"   场景数 {security.get('scenario_count')} / 运行 {security.get('runs')}")
    print(f"   错误码统计 {json.dumps(security.get('tool_error_code_counts', {}), ensure_ascii=False)}")
    print(f"   安全事件统计 {json.dumps(security.get('security_event_counts', {}), ensure_ascii=False)}")
    print(f"   环境跳过 {json.dumps(security.get('environment_skip_counts', {}), ensure_ascii=False)}")
    print()

    print("== 7. 生成核心报告 ==")
    write_benchmark_core_report(
        report_path=report_path,
        harness_artifact_path=harness_path,
        context_artifact_path=context_path,
        memory_artifact_path=memory_path,
        recovery_artifact_path=recovery_path,
    )
    print(f"   {report_path}")

    print("== 8. 生成按模块组织的指标报告 ==")
    write_module_metrics(out_dir, module_md, out_dir / "module-metrics.json")
    annotate(out_dir / "module-metrics.json")
    annotate_markdown(module_md)
    annotate_markdown(report_path)
    annotate_all(out_dir)
    print()
    print("完成。给测试者看的报告：")
    print(f"  {module_md}")
    print(f"  {report_path}")
    print(f"原始产物：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
