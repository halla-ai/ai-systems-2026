---
title: 개발 도구
description: AI 시스템 2026 강의에서 사용하는 핵심 도구 목록과 가이드
---

## 핵심 도구

### Claude Code (Anthropic)

에이전틱 코딩의 기준 상용 도구. 터미널 통합, MCP 지원, GitHub 연동.

```bash
# 설치
npm install -g @anthropic-ai/claude-code

# 기본 사용
claude "Python 계산기를 만들어줘"

# 파일 컨텍스트 포함
claude --file=PROMPT.md

# 헤드리스 모드 (Ralph 루프용)
cat PROMPT.md | claude --headless
```

**주요 기능**:
- MCP 서버 통합 (`~/.claude/settings.json`)
- `CLAUDE.md` 프로젝트별 지침 파일
- 멀티파일 편집
- GitHub Actions 통합

---

### vLLM

고처리량 LLM 추론 서버. OpenAI 호환 API 제공.

```bash
# 설치
pip install vllm

# 서버 시작
python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct \
  --port 8000

# 클라이언트 사용 (OpenAI 호환)
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="token")
```

---

### Model Context Protocol (MCP)

에이전트와 외부 도구를 연결하는 표준 프로토콜.

**주요 MCP 서버**:

| 서버 | 기능 | 설치 |
|------|------|------|
| `@modelcontextprotocol/server-filesystem` | 파일 읽기/쓰기 | `npx` |
| `mcp-server-git` | Git 작업 | `uvx` |
| `mcp-server-github` | GitHub API | `uvx` |
| `mcp-server-postgres` | PostgreSQL | `uvx` |

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/project"]
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "."]
    }
  }
}
```

---

### OpenTelemetry

에이전트 시스템 텔레메트리 수집 표준.

```python
pip install opentelemetry-sdk opentelemetry-exporter-prometheus
```

---

### DeepSeek-Coder-V2

오픈소스 코딩 특화 LLM (236B MoE, Apache 2.0).

- HuggingFace: `deepseek-ai/DeepSeek-Coder-V2-Instruct`
- Lite 버전: `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` (16B)
- 컨텍스트: 128K 토큰

---

### 기타 유용한 도구

| 도구 | 용도 | 설치 |
|------|------|------|
| `uv` | Python 패키지 관리 (pip 대체) | `pip install uv` |
| `Ruff` | Python 린터/포매터 | `pip install ruff` |
| `pytest` | Python 테스트 프레임워크 | `pip install pytest` |
| `mypy` | Python 타입 체커 | `pip install mypy` |
| `httpx` | 비동기 HTTP 클라이언트 | `pip install httpx` |
