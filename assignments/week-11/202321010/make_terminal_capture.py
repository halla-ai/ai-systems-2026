"""
make_terminal_capture.py — run_output.txt 를 터미널 스타일 PNG 이미지로 변환
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
import re
from matplotlib import font_manager

# 한글 지원 폰트 탐색 (Windows 기본 폰트 우선)
_KOREAN_FONTS = ["Malgun Gothic", "gulim", "Dotum", "Batang", "NanumGothic"]
_mono_font = "Courier New"
_ko_font   = None
for _fn in _KOREAN_FONTS:
    if any(_fn.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        _ko_font = _fn
        break

# ── 출력 파일 읽기 ────────────────────────────────────────────────────────────
with open("run_output.txt", "r", encoding="utf-8", errors="replace") as f:
    raw_lines = f.read().splitlines()

# 특수문자 치환 (폰트 미지원 글리프 방지)
_REPLACE = {
    "\u2714": "[OK]", "\u2713": "[OK]",   # ✓
    "\u2717": "[FAIL]", "\u2717": "[FAIL]", # ✗
    "\u2500": "-", "\u2502": "|",          # ─ │
    "\u2501": "=",                         # ━
    "\u25cf": "*",                         # ●
    "\u00b7": ".",                         # ·
    "\x13": "", "\x19": "",               # 제어문자
}

def sanitize(s):
    for k, v in _REPLACE.items():
        s = s.replace(k, v)
    return s

# 빈 줄 제거 후 최대 120줄
lines = [sanitize(l) for l in raw_lines if sanitize(l).strip()][:120]

# ── 컬러 규칙 ─────────────────────────────────────────────────────────────────
def line_color(text):
    t = text.strip()
    if t.startswith("[OK]") or "PASS" in t or "ALL PASS" in t:
        return "#69FF8A"       # 밝은 초록
    if t.startswith("[FAIL]") or ("FAIL" in t and "PASS" not in t):
        return "#FF6B6B"       # 빨강
    if t.startswith("===") or t.startswith("---"):
        return "#7ECFFF"       # 파랑
    if t.startswith("  run_id") or t.startswith("  closed") \
       or t.startswith("  total") or t.startswith("  task") \
       or t.startswith("  gate") or t.startswith("  artifact") \
       or t.startswith("  span"):
        return "#FFD580"       # 노랑
    if re.search(r"\[1/4\]|\[2/4\]|\[3/4\]|\[4/4\]", t):
        return "#C8A2FF"       # 보라
    if t.startswith("ralph.") or "PASS" in t:
        return "#69FF8A"
    return "#E8E8E8"           # 기본 흰색

# ── 그림 크기 계산 ─────────────────────────────────────────────────────────────
n      = len(lines)
height = max(8, n * 0.185 + 1.2)
width  = 14

fig, ax = plt.subplots(figsize=(width, height), facecolor="#1E1E1E")
ax.set_facecolor("#1E1E1E")
ax.axis("off")

# ── 상단 타이틀 바 ────────────────────────────────────────────────────────────
title_bar = mpatches.FancyBboxPatch(
    (0, 1), 1, 0.045,
    boxstyle="square,pad=0", linewidth=0,
    facecolor="#3C3C3C", transform=ax.transAxes, clip_on=False,
)
ax.add_patch(title_bar)
ax.text(0.5, 1.022, "PowerShell  —  python run_lab11.py",
        transform=ax.transAxes, ha="center", va="center",
        fontsize=9, color="#CCCCCC", fontfamily="monospace")

# 신호등 점
for xi, col in zip([0.012, 0.028, 0.044], ["#FF5F56", "#FFBD2E", "#27C93F"]):
    circ = plt.Circle((xi, 1.022), 0.007,
                       transform=ax.transAxes, color=col, clip_on=False)
    ax.add_patch(circ)

# ── 텍스트 렌더링 ─────────────────────────────────────────────────────────────
y_top  = 0.985
y_step = 0.985 / (n + 1)
fp     = FontProperties(family=_ko_font or "sans-serif", size=7.8)

for i, line in enumerate(lines):
    y     = y_top - i * y_step
    color = line_color(line)
    # 탭/긴 공백 정리
    text = line.replace("\t", "    ")
    ax.text(0.012, y, text,
            transform=ax.transAxes,
            ha="left", va="top",
            color=color,
            fontproperties=fp,
            clip_on=True)

# ── 저장 ──────────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0)
plt.savefig("terminal_capture.png", dpi=160,
            bbox_inches="tight", facecolor="#1E1E1E")
plt.close()
print("[✓] terminal_capture.png 생성 완료")
