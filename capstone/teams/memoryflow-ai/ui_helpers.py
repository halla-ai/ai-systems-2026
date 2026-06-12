"""Presentation UI helpers for the MemoryFlow AI Streamlit demo."""

import html

import streamlit as st


def memory_text(memory):
    """Return a compact display string for a memory object."""
    if not memory:
        return ""
    value = memory.get("value") or memory.get("text") or memory.get("user_input") or ""
    return str(value)


def memory_label(memory):
    """Return a stable short label for a memory object."""
    key = memory.get("key") or memory.get("type") or "memory"
    labels = {
        "name": "Name",
        "project": "Project",
        "capstone_topic": "Capstone",
        "preference": "Preference",
        "occupation": "Role",
        "conversation_summary": "Summary",
    }
    value = memory_text(memory)
    if len(value) > 72:
        value = value[:72] + "..."
    return f"{labels.get(key, key)}: {value}"


def inject_styles():
    """Install app-specific dark presentation CSS."""
    st.markdown(
        """
        <style>
        .stApp {
            background: #0b1020;
            color: #e5e7eb;
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1480px;
        }
        h1, h2, h3, h4, h5, h6, p, label, span {
            letter-spacing: 0;
        }
        section[data-testid="stSidebar"] {
            background: #090d1a;
            border-right: 1px solid #1f2937;
        }
        div[data-testid="stMetric"] {
            background: #111827;
            border: 1px solid #263244;
            border-radius: 8px;
            padding: 12px 14px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #f3f4f6;
        }
        .mf-hero {
            border-bottom: 1px solid #1f2937;
            padding-bottom: 1rem;
            margin-bottom: 1.1rem;
        }
        .mf-title {
            font-size: 1.85rem;
            line-height: 2.2rem;
            font-weight: 760;
            margin: 0;
            color: #f9fafb;
        }
        .mf-subtitle {
            margin: 0.35rem 0 0 0;
            color: #9ca3af;
            font-size: 0.95rem;
        }
        .mf-card {
            background: #111827;
            border: 1px solid #263244;
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 10px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
        }
        .mf-card-title {
            color: #d1d5db;
            font-weight: 700;
            font-size: 0.88rem;
            margin-bottom: 7px;
        }
        .mf-muted {
            color: #aab2c0;
            font-size: 0.88rem;
        }
        .mf-pill {
            display: inline-flex;
            align-items: center;
            min-height: 28px;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 0.82rem;
            font-weight: 700;
            border: 1px solid transparent;
            white-space: nowrap;
        }
        .mf-pill-on {
            background: rgba(34, 197, 94, 0.13);
            color: #86efac;
            border-color: rgba(134, 239, 172, 0.45);
        }
        .mf-pill-off {
            background: rgba(248, 113, 113, 0.13);
            color: #fca5a5;
            border-color: rgba(252, 165, 165, 0.45);
        }
        .mf-pill-neutral {
            background: rgba(148, 163, 184, 0.13);
            color: #cbd5e1;
            border-color: rgba(203, 213, 225, 0.3);
        }
        .mf-loop {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 9px;
            margin-top: 6px;
        }
        .mf-step {
            border: 1px solid #263244;
            border-radius: 8px;
            padding: 12px;
            min-height: 104px;
            background: #111827;
        }
        .mf-step-active {
            border-color: rgba(96, 165, 250, 0.65);
            background: #0f1b32;
        }
        .mf-step-skipped {
            background: #0d1322;
            color: #64748b;
        }
        .mf-step-name {
            font-size: 0.84rem;
            font-weight: 780;
            color: #bfdbfe;
        }
        .mf-step-text {
            color: #cbd5e1;
            font-size: 0.82rem;
            margin-top: 7px;
            line-height: 1.35rem;
        }
        .mf-tree {
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            color: #dbeafe;
            background: #0d1322;
            border: 1px solid #263244;
            border-radius: 8px;
            padding: 14px;
            line-height: 1.65rem;
            white-space: pre-wrap;
        }
        .mf-timeline-item {
            border-left: 2px solid #60a5fa;
            padding: 0 0 12px 12px;
            margin-left: 5px;
        }
        .mf-timeline-time {
            color: #93c5fd;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .mf-timeline-text {
            color: #e5e7eb;
            font-size: 0.9rem;
        }
        .mf-check {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #e5e7eb;
            margin: 7px 0;
        }
        .mf-check-symbol {
            color: #86efac;
            font-weight: 800;
        }
        @media (max-width: 980px) {
            .mf-loop {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    """Render the app heading."""
    st.markdown(
        """
        <div class="mf-hero">
          <p class="mf-title">MemoryFlow AI</p>
          <p class="mf-subtitle">Presentation demo for memory gating, retrieval, response quality, and reflection.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_pill(label, enabled):
    """Render a boolean status pill."""
    css = "mf-pill-on" if enabled else "mf-pill-off"
    value = "ON" if enabled else "OFF"
    st.markdown(f'<span class="mf-pill {css}">{html.escape(label)}: {value}</span>', unsafe_allow_html=True)


def render_card(title, body, muted=False):
    """Render a simple bordered content block."""
    body_class = "mf-muted" if muted else ""
    st.markdown(
        f"""
        <div class="mf-card">
          <div class="mf-card-title">{html.escape(str(title))}</div>
          <div class="{body_class}">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ralph_loop(turn):
    """Render the four-stage RALPH loop."""
    use_memory = bool(turn.get("use_memory"))
    judge_result = turn.get("judge_result") or {}
    observe = (
        f"검색된 기억 {len(turn.get('retrieved_memories') or [])}개 확인"
        if use_memory
        else "검색 생략 확인"
    )
    steps = [
        ("PLAN", f"사용자 의도 분석<br>{html.escape(turn.get('intent_label', '-'))}"),
        ("ACT", "기억 저장 또는 검색<br>" + ("Memory Gate ON" if use_memory else "Memory Gate OFF")),
        ("OBSERVE", html.escape(observe)),
        ("REFLECT", f"응답 품질 평가 및 다음 행동 결정<br>{judge_result.get('score', '-')}/5"),
    ]

    html_steps = []
    for name, text in steps:
        skipped = name in {"ACT", "OBSERVE"} and not use_memory
        css = "mf-step-skipped" if skipped else "mf-step-active"
        html_steps.append(
            f"""
            <div class="mf-step {css}">
              <div class="mf-step-name">{html.escape(name)}</div>
              <div class="mf-step-text">{text}</div>
            </div>
            """
        )

    st.markdown(f'<div class="mf-loop">{"".join(html_steps)}</div>', unsafe_allow_html=True)


def render_timeline(events):
    """Render chronological events."""
    if not events:
        st.caption("아직 기록된 이벤트가 없습니다.")
        return
    html_items = []
    for event in events[-16:]:
        html_items.append(
            f"""
            <div class="mf-timeline-item">
              <div class="mf-timeline-time">{html.escape(event.get('time', ''))}</div>
              <div class="mf-timeline-text">{html.escape(event.get('text', ''))}</div>
            </div>
            """
        )
    st.markdown("".join(html_items), unsafe_allow_html=True)


def render_memory_tree(items):
    """Render memory graph as a text tree."""
    lines = ["User"]
    for label, value in items:
        if value:
            lines.append(f"├── {label}")
            lines.append(f"│   └── {value}")
    if len(lines) == 1:
        lines.append("└── 저장된 장기 기억 없음")
    st.markdown(f'<div class="mf-tree">{html.escape(chr(10).join(lines))}</div>', unsafe_allow_html=True)


def render_reflection_summary(summary):
    """Render detailed reflection/evaluation status."""
    st.markdown(
        f"""
        <div class="mf-card">
          <div class="mf-card-title">Reflection</div>
          <div class="mf-check"><span class="mf-check-symbol">✓</span><span>{html.escape(summary.get('retrieval', 'Retrieved correct memory'))}</span></div>
          <div class="mf-check"><span class="mf-check-symbol">✓</span><span>{html.escape(summary.get('consistency', 'Response is consistent'))}</span></div>
          <div class="mf-check"><span class="mf-check-symbol">✓</span><span>Retry: {html.escape(summary.get('retry', 'Not required'))}</span></div>
          <div class="mf-check"><span class="mf-check-symbol">✓</span><span>Confidence: {html.escape(str(summary.get('confidence', '0%')))}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
