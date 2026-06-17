"""Tests for Fix↔QA and HOTL outer loops."""

from docs_code_drift_detector.human_approval import create_approval_gate, write_approval_gate
from docs_code_drift_detector.pipeline_cycles import (
    run_fix_qa_cycle,
    run_hotl_outer_loop,
    wait_for_gate_resolution,
)
from docs_code_drift_detector.qa_loop import QAResult


def test_fix_qa_cycle_calls_fix_generator_on_failure(tmp_path):
    calls: list[int] = []

    def make_patch(retry: int, _error: str) -> str:
        calls.append(retry)
        return f"patch-v{retry}"

    result = run_fix_qa_cycle(
        tmp_path,
        run_id="r1",
        max_qa_iterations=3,
        review_approved=True,
        make_patch=make_patch,
    )
    assert 0 in calls
    assert result.fix_invocations >= 1
    assert result.patch.startswith("patch-v")


def test_hotl_outer_loop_reruns_qa_when_pending(tmp_path):
    def make_patch(_retry: int, _err: str) -> str:
        return "patch"

    def run_pr(_patch: str, _qa) -> None:
        return None

    def build_gate(_qa_result, _url, hotl_flag: bool):
        if hotl_flag:
            return create_approval_gate("r1", requires_human=True, hotl_approved=True)
        return create_approval_gate("r1", requires_human=True, hotl_approved=False)

    result = run_hotl_outer_loop(
        project_root=tmp_path,
        run_id="r1",
        max_qa_iterations=1,
        max_hotl_cycles=3,
        review_approved=True,
        hotl_approved=False,
        make_patch=make_patch,
        build_gate=build_gate,
        run_pr=run_pr,
    )
    assert result.hotl_cycles >= 2
    assert result.approval_gate.status == "pending"


def test_hotl_reads_approved_gate_file(tmp_path):
    gate_path = tmp_path / "approval_gate.json"

    def make_patch(_retry: int, _err: str) -> str:
        return "patch"

    def build_gate(_qa, _url, hotl_flag: bool):
        return create_approval_gate("r3", requires_human=True, hotl_approved=hotl_flag)

    def on_event(name: str, _payload: dict) -> None:
        if name == "hotl.pending":
            approved = create_approval_gate("r3", requires_human=True, hotl_approved=True)
            from docs_code_drift_detector.human_approval import write_approval_gate
            write_approval_gate(gate_path, approved)

    result = run_hotl_outer_loop(
        project_root=tmp_path,
        run_id="r3",
        max_qa_iterations=1,
        max_hotl_cycles=3,
        review_approved=True,
        hotl_approved=False,
        make_patch=make_patch,
        build_gate=build_gate,
        run_pr=lambda _p, _q: None,
        gate_path=gate_path,
        on_event=on_event,
    )
    assert result.approval_gate.status == "approved"


def test_wait_hotl_blocks_until_approved(tmp_path):
    gate_path = tmp_path / "approval_gate.json"
    event_names: list[str] = []

    def make_patch(_retry: int, _err: str) -> str:
        return "patch"

    def build_gate(_qa, _url, hotl_flag: bool):
        return create_approval_gate("r4", requires_human=True, hotl_approved=hotl_flag)

    def on_event(name: str, _payload: dict) -> None:
        event_names.append(name)
        if name == "hotl.waiting":
            approved = create_approval_gate("r4", requires_human=True, hotl_approved=True)
            write_approval_gate(gate_path, approved)

    result = run_hotl_outer_loop(
        project_root=tmp_path,
        run_id="r4",
        max_qa_iterations=1,
        max_hotl_cycles=3,
        review_approved=True,
        hotl_approved=False,
        make_patch=make_patch,
        build_gate=build_gate,
        run_pr=lambda _p, _q: None,
        gate_path=gate_path,
        wait_hotl=True,
        wait_hotl_timeout_sec=5.0,
        wait_hotl_poll_sec=0.01,
        sleep_fn=lambda _sec: None,
        on_event=on_event,
    )
    assert result.hotl_waited is True
    assert result.hotl_timed_out is False
    assert result.approval_gate.status == "approved"
    assert "hotl.waiting" in event_names
    assert "hotl.approved" in event_names


def test_wait_hotl_times_out(tmp_path):
    gate_path = tmp_path / "approval_gate.json"
    pending = create_approval_gate("r5", requires_human=True, hotl_approved=False)
    write_approval_gate(gate_path, pending)

    result = run_hotl_outer_loop(
        project_root=tmp_path,
        run_id="r5",
        max_qa_iterations=1,
        max_hotl_cycles=3,
        review_approved=True,
        hotl_approved=False,
        make_patch=lambda _r, _e: "",
        build_gate=lambda _qa, _url, flag: create_approval_gate(
            "r5", requires_human=True, hotl_approved=flag,
        ),
        run_pr=lambda _p, _q: None,
        gate_path=gate_path,
        wait_hotl=True,
        wait_hotl_timeout_sec=0.05,
        wait_hotl_poll_sec=0.01,
        sleep_fn=lambda _sec: None,
    )
    assert result.hotl_waited is True
    assert result.hotl_timed_out is True
    assert result.approval_gate.status == "pending"


def test_wait_for_gate_resolution_finds_approved(tmp_path):
    gate_path = tmp_path / "approval_gate.json"
    write_approval_gate(
        gate_path,
        create_approval_gate("r6", requires_human=True, hotl_approved=True),
    )
    resolved = wait_for_gate_resolution(
        gate_path, timeout_sec=1.0, poll_sec=0.01, sleep_fn=lambda _s: None,
    )
    assert resolved is not None
    assert resolved.status == "approved"


def test_hotl_approved_completes_gate(tmp_path):
    def make_patch(_retry: int, _err: str) -> str:
        return ""

    result = run_hotl_outer_loop(
        project_root=tmp_path,
        run_id="r2",
        max_qa_iterations=1,
        max_hotl_cycles=3,
        review_approved=True,
        hotl_approved=True,
        make_patch=make_patch,
        build_gate=lambda _qa, _url, flag: create_approval_gate(
            "r2", requires_human=False, hotl_approved=flag,
        ),
        run_pr=lambda _p, _q: None,
    )
    assert result.approval_gate.status == "approved"
