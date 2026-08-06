"""CLI entry point for docs-code drift detector."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docs_code_drift_detector.benchmark_runner import BENCHMARK_PROJECT, run_benchmark
from docs_code_drift_detector.config import AppConfig
from docs_code_drift_detector.demo_interactive import run_interactive_hotl
from docs_code_drift_detector.demo_summary import print_run_evidence
from docs_code_drift_detector.eval_runner import run_repeatability_eval
from docs_code_drift_detector.human_approval import load_approval_gate, update_gate_status, write_approval_gate
from docs_code_drift_detector.orchestrator import run_pipeline
from docs_code_drift_detector.replay_tools import format_replay_report, write_replay_summary


def scan_project(
    project_root: Path,
    output_dir: Path | None = None,
    *,
    dry_run_pr: bool = False,
    create_pr: bool = False,
    use_llm: bool = False,
    detect_semantic: bool = False,
    max_qa_iterations: int = 5,
    max_hotl_cycles: int = 5,
    hotl_approved: bool = False,
    wait_hotl: bool = False,
    wait_hotl_timeout: int = 300,
    on_progress=None,
):
    """Run the full multi-agent drift detection pipeline."""
    config = AppConfig.from_env(
        use_llm=use_llm or detect_semantic,
        detect_semantic=detect_semantic,
        create_pr=create_pr,
        dry_run_pr=dry_run_pr,
        hotl_approved=hotl_approved,
        wait_hotl=wait_hotl,
        wait_hotl_timeout_sec=float(wait_hotl_timeout),
        max_qa_iterations=max_qa_iterations,
    )
    return run_pipeline(
        project_root,
        output_dir,
        dry_run_pr=config.dry_run_pr,
        create_pr=config.create_pr,
        use_llm=config.use_llm,
        max_qa_iterations=config.max_qa_iterations,
        max_hotl_cycles=max_hotl_cycles,
        hotl_approved=config.hotl_approved,
        config=config,
        on_progress=on_progress,
    )


def _pr_failure_from_events(events_path: Path) -> str | None:
    if not events_path.exists():
        return None
    for line in reversed(events_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event_type") != "pr.created":
            continue
        payload = event.get("payload") or {}
        if payload.get("pr_url"):
            return None
        return payload.get("error") or payload.get("summary") or "PR creation failed (see events)"
    return None


def gate_command(output_dir: Path, status: str) -> int:
    gate_path = output_dir / "approval_gate.json"
    gate = load_approval_gate(gate_path)
    if gate is None:
        print(f"Gate not found: {gate_path}", file=sys.stderr)
        return 1
    updated = update_gate_status(gate, status)
    write_approval_gate(gate_path, updated)
    print(f"Gate updated: {updated.status}")
    print(f"File:       {gate_path}")
    print(f"Message:    {updated.message}")
    return 0


def replay_command(output_dir: Path, run_id: str | None = None) -> int:
    if not output_dir.exists():
        print(f"Output dir not found: {output_dir}", file=sys.stderr)
        return 1
    print(format_replay_report(output_dir, run_id=run_id))
    summary_path = write_replay_summary(output_dir, run_id=run_id)
    print(f"\nSummary: {summary_path}")
    return 0


def _print_scan_result(result, out_dir: Path, args) -> int:
    report = result.report
    print(f"Run ID:   {result.run_id}")
    print(f"Provider: {result.provider_profile}")
    if result.llm_meta.get("llm_used"):
        print(f"LLM cost: ~${result.llm_meta.get('estimated_cost_usd', 0):.4f}")
    print(f"Scanned {report.functions_scanned} functions.")
    print(f"Found {len(report.drifts)} drift(s).")
    print(f"QA passed: {result.qa_passed}")
    print(f"Review:   {result.review_verdict.get('verdict', 'n/a')}")
    if result.review_verdict.get("abort_reason"):
        print(f"Aborted:  {result.review_verdict['abort_reason']}")
    print(f"Report:   {out_dir / 'drift_report.json'}")
    print(f"QA:       {out_dir / 'qa_result.json'}")
    print(f"Events:   {out_dir / '.events.jsonl'}")
    print(f"Patch:    {out_dir / 'patch.diff'}")
    if result.hotl_waited:
        if result.hotl_timed_out:
            print("HOTL:     timed out waiting for approval (gate still pending)")
        else:
            print("HOTL:     waited for human approval in-process")
    if result.pr_url:
        print(f"PR URL:   {result.pr_url}")
    elif getattr(args, "create_pr", False):
        pr_note = "PR not created."
        if not report.drifts:
            pr_note += " No drifts detected."
        else:
            detail = _pr_failure_from_events(out_dir / ".events.jsonl")
            if detail:
                pr_note += f" Reason: {detail}"
        print(f"PR:       {pr_note}")
    elif (out_dir / "pr_dry_run.txt").exists():
        print(f"PR preview: {out_dir / 'pr_dry_run.txt'}")
    return 1 if report.drifts else 0


def demo_command(
    project_root: Path,
    output_dir: Path | None,
    *,
    create_pr: bool = False,
    wait_hotl: bool = False,
    wait_hotl_timeout: int = 300,
    interactive: bool = True,
) -> int:
    """
    One-command live demo: full pipeline + end-of-run evidence summary.
    Default: LLM + semantic + PR dry-run, then prompt Enter→PR / n→revise.
    """
    def _progress(msg: str) -> None:
        print(msg, flush=True)

    out_dir = output_dir or (project_root / "output")
    use_interactive = interactive and not create_pr and not wait_hotl
    hotl_approved = not wait_hotl and not use_interactive

    if wait_hotl:
        print(f"HOTL: run in another window when waiting:\n"
              f"  python -m docs_code_drift_detector gate -o {out_dir} approved\n")

    result = scan_project(
        project_root,
        out_dir,
        use_llm=True,
        detect_semantic=True,
        dry_run_pr=not create_pr,
        create_pr=create_pr,
        hotl_approved=hotl_approved,
        wait_hotl=wait_hotl,
        wait_hotl_timeout=wait_hotl_timeout,
        max_hotl_cycles=1 if use_interactive else 5,
        on_progress=_progress,
    )

    class _Args:
        pass

    args = _Args()
    args.create_pr = create_pr
    code = _print_scan_result(result, out_dir, args)
    print_run_evidence(result, out_dir)

    if use_interactive:
        result = run_interactive_hotl(result, project_root, out_dir)
        if result.pr_url:
            print(f"\nPR URL: {result.pr_url}")
            print_run_evidence(result, out_dir)

    return code


def benchmark_command(
    project_root: Path,
    output_dir: Path,
    *,
    use_llm: bool = False,
    detect_semantic: bool = False,
    full_pipeline: bool = False,
) -> int:
    cfg = AppConfig.from_env(use_llm=use_llm, detect_semantic=detect_semantic or use_llm)
    if use_llm and not cfg.openai_api_key:
        print(
            "Warning: --use-llm but OPENAI_API_KEY not set; LLM steps use heuristic fallback.",
            file=sys.stderr,
        )

    report = run_benchmark(
        project_root,
        output_dir,
        use_llm=use_llm,
        detect_semantic=detect_semantic or use_llm,
        full_pipeline=full_pipeline,
    )
    curated = report.get("curated", report["metrics"])
    realistic = report.get("realistic_fixtures", {})
    proposal = report.get("proposal_section4", {})

    llm_mode = "on" if report.get("use_llm") else "off"
    semantic_mode = "on" if report.get("detect_semantic") else "off"
    print(f"Mode:        {report['mode']}")
    print(f"LLM:         {llm_mode}  (semantic: {semantic_mode})")
    print("")
    print("=== Proposal S4: 30-function benchmark ===")
    if proposal:
        ts = proposal.get("test_set", {})
        det = proposal.get("detection", {})
        pipe = proposal.get("pipeline", {})
        perf = proposal.get("performance", {})
        print(f"Test set:    {ts.get('intentional_drift_functions', '?')} drifts + "
              f"{ts.get('clean_functions', '?')} clean = {ts.get('total_functions', '?')} functions")
        print(f"Precision:   {det.get('precision')}  (target >= {proposal['targets'].get('min_precision', 0.7)})")
        print(f"Recall:      {det.get('recall')}  (target >= {proposal['targets'].get('min_recall', 0.7)})")
        print(f"FPR:         {det.get('false_positive_rate')}  (target <= {proposal['targets'].get('max_false_positive_rate', 0.15)})")
        if pipe.get("ran"):
            print(f"QA passed:   {pipe.get('qa_passed')}  (PR success rate {pipe.get('pr_success_rate')})")
            print(f"Latency:     {perf.get('total_latency_sec')}s  (target <= {proposal['targets'].get('max_latency_sec', 120)}s)")
            llm_info = pipe.get("llm") or {}
            if report.get("use_llm"):
                used = "yes" if llm_info.get("llm_used") else "no (fallback)"
                print(f"LLM used:    {used}  provider={llm_info.get('provider') or 'n/a'}")
            if pipe.get("llm_cost_usd") is not None:
                print(f"LLM cost:    ${pipe.get('llm_cost_usd')}  (target <= ${proposal['targets'].get('max_cost_usd', 0.5)})")
        print(f"Overall:     {'PASS' if proposal.get('overall_pass') else 'FAIL'}")
    print("")
    print("=== Realistic fixture (honest metrics) ===")

    if realistic:
        for name, m in realistic.items():
            print(f"Fixture:     {name}")
            print(f"Functions:   {m['functions_scanned']}")
            print(f"Precision:   {m['precision']}  (target >= {m['targets'].get('min_precision', 0.7)})")
            print(f"Recall:      {m['recall']}  (target >= {m['targets'].get('min_recall', 0.7)})")
            print(f"True drifts: {m['true_positives']}/{m['expected_drifts']} found (recall {m['recall']})")
            print(f"Detections:  {m['detected_drifts']} total = {m['true_positives']} correct + {m['false_positives']} extra")
            if m.get("known_false_positives_hit"):
                print(f"Known FP:    {', '.join(m['known_false_positives_hit'])}  (precision {m['precision']})")
            if m.get("unexpected"):
                print(f"Other FP:    {', '.join(m['unexpected'])}")
            print(f"Overall:     {'PASS' if m['overall_pass'] else 'FAIL'}")
    else:
        m = curated
        print(f"Precision:   {m['precision']}")
        print(f"Recall:      {m['recall']}")

    print("")
    print("--- Synthetic regression set (40 fn, optional) ---")
    print(f"Precision:   {curated['precision']}  Recall: {curated['recall']}  (detector-tuned; optimistic)")
    print(f"Project:     {report['project']}")

    if report.get("report_path"):
        print(f"\nReport:      {report['report_path']}")

    proposal_pass = proposal.get("overall_pass", curated.get("overall_pass", False))
    realistic_pass = all(m.get("overall_pass", False) for m in realistic.values()) if realistic else True
    if report["mode"] == "full_pipeline":
        return 0 if proposal_pass and realistic_pass else 1
    return 0 if proposal_pass else 1


def eval_command(
    project_root: Path,
    output_dir: Path,
    *,
    runs: int = 3,
    use_llm: bool = False,
    detect_semantic: bool = False,
) -> int:
    summary = run_repeatability_eval(
        project_root,
        output_dir,
        runs=runs,
        dry_run_pr=True,
        use_llm=use_llm,
        detect_semantic=detect_semantic,
    )
    print(f"Project:    {summary['project']}")
    print(f"Runs:       {summary['runs']}")
    print(f"Repeatable: {summary['repeatable']}")
    print(f"Drift counts: {summary['drift_counts']}")
    fe = summary.get("fixture_eval", {})
    if fe.get("scored"):
        print(f"Fixture eval: pass={fe.get('overall_pass')} function_recall={fe.get('function_recall')}")
    print(f"Summary:    {output_dir / 'eval_summary.json'}")
    return 0 if summary.get("repeatable") else 1


def main(argv: list[str] | None = None) -> int:
    parser = __import__("argparse").ArgumentParser(
        prog="docs_code_drift_detector",
        description="Detect drift between Python code and documentation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a project for drift")
    scan_parser.add_argument("path", type=Path, nargs="?", default=Path("."))
    scan_parser.add_argument("-o", "--output", type=Path, default=None)
    scan_parser.add_argument("--dry-run-pr", action="store_true")
    scan_parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Create real GitHub PR via gh (requires --hotl-approved, git, gh auth)",
    )
    scan_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for doc parsing refinement (OPENAI_API_KEY required)",
    )
    scan_parser.add_argument(
        "--detect-semantic",
        action="store_true",
        help="LLM semantic mismatch candidates (HITL only, no auto patch)",
    )
    scan_parser.add_argument("--max-qa-iterations", type=int, default=5)
    scan_parser.add_argument("--max-hotl-cycles", type=int, default=5)
    scan_parser.add_argument("--hotl-approved", action="store_true")
    scan_parser.add_argument(
        "--wait-hotl",
        action="store_true",
        help="Block until approval_gate.json is approved/rejected (same scan process)",
    )
    scan_parser.add_argument(
        "--wait-hotl-timeout",
        type=int,
        default=300,
        help="Seconds to wait for human gate decision (default 300)",
    )

    replay_parser = subparsers.add_parser("replay", help="Replay event log for a run output dir")
    replay_parser.add_argument("-o", "--output", type=Path, required=True)
    replay_parser.add_argument("--run-id", type=str, default=None)

    gate_parser = subparsers.add_parser("gate", help="Set human approval gate status (HOTL)")
    gate_parser.add_argument("-o", "--output", type=Path, required=True)
    gate_parser.add_argument(
        "status",
        choices=["approved", "rejected", "pending"],
        help="Human decision written to approval_gate.json",
    )

    eval_parser = subparsers.add_parser("eval", help="Run repeatability + fixture evaluation")
    eval_parser.add_argument("path", type=Path)
    eval_parser.add_argument("-o", "--output", type=Path, required=True)
    eval_parser.add_argument("-n", "--runs", type=int, default=3)
    eval_parser.add_argument("--use-llm", action="store_true")
    eval_parser.add_argument("--detect-semantic", action="store_true")

    demo_parser = subparsers.add_parser(
        "demo",
        help="Live demo: one command runs full pipeline + prints evidence summary",
    )
    demo_parser.add_argument("path", type=Path, nargs="?", default=Path("testproject"))
    demo_parser.add_argument("-o", "--output", type=Path, default=None)
    demo_parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Create real GitHub PR (default: dry-run preview)",
    )
    demo_parser.add_argument(
        "--wait-hotl",
        action="store_true",
        help="Block until gate approved (use gate subcommand in 2nd terminal)",
    )
    demo_parser.add_argument("--wait-hotl-timeout", type=int, default=120)
    demo_parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip post-run Enter→PR / n→revise prompt",
    )

    bench_parser = subparsers.add_parser(
        "benchmark",
        help="Proposal §4: 30-function precision/recall/FPR evaluation",
    )
    bench_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=BENCHMARK_PROJECT,
    )
    bench_parser.add_argument("-o", "--output", type=Path, default=None)
    bench_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM doc review, drift filter, README patch (OPENAI_API_KEY)",
    )
    bench_parser.add_argument(
        "--detect-semantic",
        action="store_true",
        help="LLM semantic drift candidates (HITL only; implied by --use-llm)",
    )
    bench_parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run closed-loop scan+Fix+QA+PR dry-run (proposal §4 pipeline targets)",
    )
    bench_parser.add_argument(
        "--detection-only",
        action="store_true",
        help="Detection metrics only (skip pipeline; faster)",
    )

    args = parser.parse_args(argv)

    if args.command == "scan":
        def _live_progress(msg: str) -> None:
            print(msg, flush=True)

        result = scan_project(
            args.path,
            args.output,
            dry_run_pr=args.dry_run_pr,
            create_pr=args.create_pr,
            use_llm=args.use_llm,
            detect_semantic=args.detect_semantic,
            max_qa_iterations=args.max_qa_iterations,
            max_hotl_cycles=args.max_hotl_cycles,
            hotl_approved=args.hotl_approved,
            wait_hotl=args.wait_hotl,
            wait_hotl_timeout=args.wait_hotl_timeout,
            on_progress=_live_progress if args.wait_hotl or args.use_llm else None,
        )
        out_dir = args.output or args.path.resolve()
        return _print_scan_result(result, out_dir, args)

    if args.command == "replay":
        return replay_command(args.output, run_id=args.run_id)

    if args.command == "gate":
        return gate_command(args.output, args.status)

    if args.command == "eval":
        return eval_command(
            args.path,
            args.output,
            runs=args.runs,
            use_llm=args.use_llm,
            detect_semantic=args.detect_semantic,
        )

    if args.command == "demo":
        return demo_command(
            args.path,
            args.output,
            create_pr=args.create_pr,
            wait_hotl=args.wait_hotl,
            wait_hotl_timeout=args.wait_hotl_timeout,
            interactive=not args.no_interactive,
        )

    if args.command == "benchmark":
        out = args.output or Path("benchmark_out")
        full_pipeline = args.full_pipeline and not args.detection_only
        return benchmark_command(
            args.path,
            out,
            use_llm=args.use_llm,
            detect_semantic=args.detect_semantic,
            full_pipeline=full_pipeline,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
