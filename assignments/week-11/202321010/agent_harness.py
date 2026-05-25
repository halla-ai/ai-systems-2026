"""
Lab 11 — RALPH Loop Agent Harness with OpenTelemetry Tracing

RALPH = Reason → Act → Look → Plan → Handle

Required span attributes (7개):
  run.id, task.id, agent.role, model.name,
  tool.name, gate.result, artifact.path
"""

import time
import uuid
import json
import random
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from events_logger import EventsLogger

# ── OTel 초기화 ───────────────────────────────────────────────────────────────
_span_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("lab11.agent", "1.0.0")

# ── 시뮬레이션 상수 ────────────────────────────────────────────────────────────
TOOLS = {
    "web_search":    lambda q: (f"Search results for '{q[:30]}'",    random.randint(200, 800)),
    "code_executor": lambda c: (f"Executed snippet: {c[:25]}...",      random.randint(100, 400)),
    "file_writer":   lambda p: (f"Written to {p}",                     random.randint(50, 200)),
    "summarizer":    lambda t: (f"Summary ({len(t)} chars)",           random.randint(300, 600)),
    "validator":     lambda d: ("valid" if len(d) > 10 else "invalid", random.randint(80, 200)),
}

COST_PER_TOKEN = 0.000002  # $2 / 1M tokens

REQUIRED_ATTRS = [
    "run.id", "task.id", "agent.role", "model.name",
    "tool.name", "gate.result", "artifact.path",
]


def _set_all_attrs(span, run_id, task_id, agent_role, model_name,
                   tool_name, gate_result, artifact_path):
    """7개 필수 span attribute를 한 번에 설정"""
    span.set_attribute("run.id",        run_id)
    span.set_attribute("task.id",       task_id)
    span.set_attribute("agent.role",    agent_role)
    span.set_attribute("model.name",    model_name)
    span.set_attribute("tool.name",     tool_name)
    span.set_attribute("gate.result",   gate_result)
    span.set_attribute("artifact.path", artifact_path)


class RalphAgent:
    """RALPH 루프 기반 에이전트 (Reason → Act → Look → Plan → Handle)"""

    def __init__(self, run_id: str, logger: EventsLogger):
        self.run_id = run_id
        self.logger = logger
        self.total_cost = 0.0

    def run_task(self, task_id: str, task_desc: str,
                 agent_role: str, model_name: str) -> tuple:
        """단일 태스크 RALPH 루프 실행"""
        task_cost = 0.0
        artifact_path = f"artifacts/{task_id}/output.json"

        with tracer.start_as_current_span("ralph.task") as task_span:
            _set_all_attrs(task_span, self.run_id, task_id, agent_role,
                           model_name, "none", "pending", "none")

            self.logger.log_event("task.start", {
                "task_id": task_id, "agent_role": agent_role,
                "model": model_name, "description": task_desc,
            })

            # ── R: Reason ────────────────────────────────────────────────────
            with tracer.start_as_current_span("ralph.reason") as span:
                _set_all_attrs(span, self.run_id, task_id, agent_role,
                               model_name, "none", "pending", "none")
                tokens = random.randint(100, 300)
                cost   = tokens * COST_PER_TOKEN
                task_cost     += cost
                self.total_cost += cost
                self.logger.log_event("step.reason", {
                    "task_id": task_id,
                    "reasoning": f"[{agent_role}] Reasoning about: {task_desc}",
                    "tokens": tokens, "cost": cost,
                })
                time.sleep(0.04)

            # ── A: Act (tool call) ───────────────────────────────────────────
            tool_name = random.choice(list(TOOLS.keys()))
            tool_fn   = TOOLS[tool_name]
            result_str, tokens = tool_fn(task_desc)
            cost = tokens * COST_PER_TOKEN
            task_cost     += cost
            self.total_cost += cost

            with tracer.start_as_current_span("ralph.act") as span:
                _set_all_attrs(span, self.run_id, task_id, agent_role,
                               model_name, tool_name, "pending", "none")
                task_span.set_attribute("tool.name", tool_name)
                self.logger.log_event("tool.call", {
                    "task_id": task_id, "tool_name": tool_name,
                    "input": task_desc[:50], "result": result_str,
                    "tokens": tokens, "cost": cost,
                })
                time.sleep(0.04)

            # ── L: Look ──────────────────────────────────────────────────────
            with tracer.start_as_current_span("ralph.look") as span:
                _set_all_attrs(span, self.run_id, task_id, agent_role,
                               model_name, tool_name, "pending", "none")
                self.logger.log_event("step.look", {
                    "task_id": task_id,
                    "observation": f"Observed: {result_str}",
                })
                time.sleep(0.03)

            # ── P: Plan (gate check) ─────────────────────────────────────────
            gate_result = "pass" if random.random() > 0.25 else "fail"

            with tracer.start_as_current_span("ralph.plan") as span:
                _set_all_attrs(span, self.run_id, task_id, agent_role,
                               model_name, tool_name, gate_result, "none")
                task_span.set_attribute("gate.result", gate_result)
                self.logger.log_event("gate.check", {
                    "task_id": task_id, "gate_result": gate_result,
                })
                time.sleep(0.03)

            # ── H: Handle (artifact 저장) ────────────────────────────────────
            output = {
                "task_id": task_id, "agent_role": agent_role,
                "model": model_name, "tool": tool_name,
                "gate": gate_result, "result": result_str,
            }
            with tracer.start_as_current_span("ralph.handle") as span:
                _set_all_attrs(span, self.run_id, task_id, agent_role,
                               model_name, tool_name, gate_result, artifact_path)
                task_span.set_attribute("artifact.path", artifact_path)
                self.logger.log_event("artifact.save", {
                    "task_id": task_id,
                    "artifact_path": artifact_path,
                    "output": output,
                })
                time.sleep(0.03)

            self.logger.log_event("task.end", {
                "task_id": task_id, "gate_result": gate_result,
                "artifact_path": artifact_path,
                "cost": round(task_cost, 8),
                "closed": gate_result == "pass",
            })

        return output, gate_result, artifact_path


# ── 스팬 JSON 내보내기 ──────────────────────────────────────────────────────────
def export_spans(run_id: str) -> str:
    spans = _span_exporter.get_finished_spans()
    records = []
    for s in spans:
        attrs = dict(s.attributes) if s.attributes else {}
        missing = [a for a in REQUIRED_ATTRS if a not in attrs]
        records.append({
            "span_name":       s.name,
            "trace_id":        format(s.context.trace_id, "032x"),
            "span_id":         format(s.context.span_id,  "016x"),
            "start_ns":        s.start_time,
            "end_ns":          s.end_time,
            "attributes":      attrs,
            "has_all_7_attrs": len(missing) == 0,
            "missing_attrs":   missing,
        })

    out = f"otel_spans_{run_id}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"[✓] OTel spans  : {out}  ({len(records)} spans)")
    return out


# ── 메인 하네스 실행 ────────────────────────────────────────────────────────────
def run_harness() -> tuple:
    random.seed(42)
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    logger = EventsLogger(run_id)

    TASKS = [
        ("task-001", "Analyze AI systems performance data",      "planner",     "gpt-4o"),
        ("task-002", "Execute data preprocessing pipeline",      "executor",    "claude-3-5-sonnet"),
        ("task-003", "Review output quality metrics",            "reviewer",    "gemini-1.5-pro"),
        ("task-004", "Synthesize final experiment report",       "synthesizer", "llama-3.1-70b"),
        ("task-005", "Validate and store result artifacts",      "executor",    "gpt-4o"),
    ]

    with tracer.start_as_current_span("ralph.run") as run_span:
        _set_all_attrs(run_span, run_id, "none", "orchestrator",
                       "none", "none", "pending", "none")

        logger.log_event("run.start", {"run_id": run_id})

        agent = RalphAgent(run_id, logger)

        for task_id, desc, role, model in TASKS:
            agent.run_task(task_id, desc, role, model)

        run_span.set_attribute("gate.result",   "pass")
        run_span.set_attribute("artifact.path", f"artifacts/{run_id}/run_summary.json")

        logger.log_event("run.end", {
            "run_id":           run_id,
            "total_cost_usd":   round(agent.total_cost, 8),
            "tasks_completed":  len(TASKS),
            "closed":           True,
        })

    logger.close()
    spans_file = export_spans(run_id)

    print(f"[✓] Events JSONL: {logger.filepath}")
    print(f"[✓] Total cost  : ${agent.total_cost:.6f}")
    return run_id, agent.total_cost, logger.filepath, spans_file


if __name__ == "__main__":
    run_harness()
