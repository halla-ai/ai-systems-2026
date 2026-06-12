"""Gemini-backed response generation for MemoryFlow AI."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai


ROOT_DIR = Path(__file__).resolve().parents[1]
MISSING_GEMINI_API_KEY_MESSAGE = "Gemini API Key가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY를 추가해주세요."
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"


class ResponseGenerator:
    """Generate final natural-language responses with Gemini only."""

    def __init__(self, model_name=None):
        load_dotenv(ROOT_DIR / ".env")
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        print(f"Gemini API key configured: {bool(self.api_key)}")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        print(f"Gemini model configured: {self.model_name}")
        self.last_gemini_error = None
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def is_configured(self):
        """Return True when Gemini can be called."""
        return bool(self.client)

    def generate_response(
        self,
        user_input,
        replayed_memories,
        intent_analysis=None,
        memory_gate_result=None,
        judge_result=None,
    ):
        """Return Gemini's final response grounded in MemoryFlow outputs."""
        if not self.client:
            return MISSING_GEMINI_API_KEY_MESSAGE

        prompt = self._build_gemini_prompt(
            user_input=user_input,
            replayed_memories=replayed_memories,
            intent_analysis=intent_analysis or {},
            memory_gate_result=memory_gate_result or {},
            judge_result=judge_result,
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
        except Exception as exc:
            self.last_gemini_error = self._gemini_error_details(exc)
            self._log_gemini_exception(exc)
            return self._demo_safe_fallback(user_input, replayed_memories, exc)

        self.last_gemini_error = None
        return (getattr(response, "text", "") or "").strip() or "Gemini가 빈 응답을 반환했습니다."

    def _log_gemini_exception(self, exc):
        """Print complete Gemini exception diagnostics for local debugging."""
        details = self.last_gemini_error or self._gemini_error_details(exc)
        print(f"Gemini exception type: {details['type']}")
        print(f"Gemini exception status code: {details['status_code']}")
        print(f"Gemini exception message: {details['message']}")
        print(f"Gemini exception model: {self.model_name}")
        print(f"Gemini exception is 429 quota/rate limit: {details['status_code'] == 429}")

    def _gemini_error_details(self, exc):
        """Return status and message details from a Gemini exception."""
        status_code = self._extract_status_code(exc)
        return {
            "type": f"{type(exc).__module__}.{type(exc).__name__}",
            "status_code": status_code if status_code is not None else "unavailable",
            "message": getattr(exc, "message", None) or str(exc),
            "model": self.model_name,
        }

    def _extract_status_code(self, exc):
        for attr in ("status_code", "status", "code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(exc, "response", None)
        for attr in ("status_code", "status"):
            value = getattr(response, attr, None)
            if isinstance(value, int):
                return value
        return None

    def _demo_safe_fallback(self, user_input, replayed_memories, exc):
        """Return a presentation-safe response when Gemini is unreachable."""
        memory_count = len(replayed_memories or [])
        details = self.last_gemini_error or self._gemini_error_details(exc)
        if details.get("status_code") == 429:
            return (
                "Gemini free quota/rate limit exceeded, but MemoryFlow pipeline still ran.\n\n"
                f"현재 입력: {user_input}\n"
                f"검색된 기억 수: {memory_count}\n"
                f"Gemini 오류: {details['type']}\n"
                f"상태 코드: {details['status_code']}"
            )
        return (
            "Gemini 연결에 실패해 데모용 안전 응답으로 전환했습니다. "
            "MemoryFlow 파이프라인은 정상적으로 실행되어 Memory Gate, 기억 검색, Judge, Reflection 흐름은 유지되었습니다.\n\n"
            f"현재 입력: {user_input}\n"
            f"검색된 기억 수: {memory_count}\n"
            f"연결 오류: {type(exc).__name__}"
        )

    def _build_gemini_prompt(
        self,
        user_input,
        replayed_memories,
        intent_analysis,
        memory_gate_result,
        judge_result=None,
    ):
        """Build the only prompt used for final response generation."""
        memories = self._format_memories(replayed_memories)
        gate = self._format_mapping(memory_gate_result) or "정보 없음"
        intent = self._format_mapping(intent_analysis) or "정보 없음"
        judge = self._format_mapping(judge_result) if judge_result else "아직 Judge 결과 없음"

        return f"""당신은 MemoryFlow AI의 최종 응답 생성기입니다.

역할:
- MemoryGate, ReplayEngine, Judge, ReflectionManager, MemoryStore의 역할을 대신하지 마세요.
- 아래에 제공된 사용자 입력, 검색된 기억, Memory Gate 결과, Judge 결과만 참고해 최종 자연어 답변만 작성하세요.
- 검색된 기억이 있으면 그 내용을 우선 사용하세요.
- 검색된 기억이 없으면 기억이 없다고 자연스럽게 말하고 필요한 정보를 요청하세요.
- 한국어로 자연스럽고 간결하게 답하세요.
- 내부 파이프라인 이름이나 JSON을 그대로 노출하지 마세요.

[User input]
{user_input}

[Retrieved memories]
{memories}

[Memory Gate result]
{gate}

[Intent analysis]
{intent}

[Judge result]
{judge}

최종 답변:"""

    def _format_memories(self, replayed_memories):
        if not replayed_memories:
            return "검색된 기억 없음"

        lines = []
        for index, memory in enumerate(replayed_memories, start=1):
            if not isinstance(memory, dict):
                lines.append(f"{index}. {memory}")
                continue
            memory_type = memory.get("type", "unknown")
            key = memory.get("key", "")
            value = memory.get("value") or memory.get("text") or memory.get("user_input") or ""
            importance = memory.get("importance", "")
            lines.append(f"{index}. type={memory_type}, key={key}, value={value}, importance={importance}")
        return "\n".join(lines)

    def _format_mapping(self, data):
        if not data:
            return ""
        if not isinstance(data, dict):
            return str(data)
        return "\n".join(f"- {key}: {value}" for key, value in data.items())

    def _project_response(self, facts, summary):
        """Create a natural project-status response from facts and summary."""
        name = facts.get("name", {}).get("value")
        project = facts.get("project", {}).get("value")
        capstone = facts.get("capstone_topic", {}).get("value")
        prefix = f"이전 기억을 보면, {name}님은 " if name else "이전 기억을 보면, 사용자는 "

        if project and capstone:
            detail = (
                f"{project}{self._particle_eul(project)} 만들고 있고, "
                f"AI Systems 캡스톤으로 {capstone}{self._particle_eul(capstone)} 진행 중입니다"
            )
        elif project:
            detail = f"{project}{self._particle_eul(project)} 만들고 있습니다"
        elif capstone:
            detail = f"AI Systems 캡스톤으로 {capstone}{self._particle_eul(capstone)} 진행 중입니다"
        else:
            detail = ""

        if detail:
            tail = " 즉, 현재는 저장된 장기 기억을 기준으로 이 작업들을 함께 진행하는 상태로 이해하고 있습니다."
            if summary:
                tail += f" 최근 요약도 같은 흐름을 가리킵니다: {summary.get('text', '')}"
            return prefix + detail + "." + tail

        return "프로젝트 관련 memory가 아직 충분하지 않습니다. 어떤 프로젝트를 진행 중인지 알려주시면 저장하겠습니다."

    def _summary_response(self, facts, summary):
        """Answer broad recent-activity questions with facts plus summary."""
        name = facts.get("name", {}).get("value")
        project = facts.get("project", {}).get("value")
        capstone = facts.get("capstone_topic", {}).get("value")
        subject = f"{name}님은" if name else "사용자는"

        sentences = []
        if project:
            sentences.append(f"{subject} {project}{self._particle_eul(project)} 만들고 있는 것으로 기억합니다")
        if capstone:
            sentences.append(f"캡스톤 주제는 {capstone}입니다")
        if summary:
            sentences.append(f"최근 대화 요약은 '{summary.get('text', '')}'입니다")

        if sentences:
            return "이전 기억을 종합하면, " + ". ".join(sentences) + "."
        return "최근 작업 흐름을 요약할 만한 memory가 아직 충분하지 않습니다."

    def _remember_response(self, user_input, intent_analysis):
        """Acknowledge newly provided facts with less template-like wording."""
        target = intent_analysis.get("target", "fact")
        extracted = self._extract_value(user_input)
        if target == "name" and extracted:
            return f"{extracted}님, 이름 정보를 장기 기억으로 저장해 두겠습니다."
        if target == "capstone_topic" and extracted:
            return f"캡스톤 주제 {extracted}를 중요한 memory로 저장하겠습니다."
        if target == "project" and extracted:
            return f"좋습니다. 현재 진행 중인 프로젝트를 {extracted}{self._particle_ro(extracted)} 기억하겠습니다."
        if target == "preference" and extracted:
            return f"{extracted}에 대한 선호를 기억해 두겠습니다."
        return "중요한 정보로 판단해 memory에 저장하겠습니다."

    def _contextual_general_response(self, user_input, facts, summary):
        """Use memory context even for general chat."""
        hints = []
        if "project" in facts:
            hints.append(f"프로젝트 memory({facts['project']['value']})")
        if "capstone_topic" in facts:
            hints.append(f"캡스톤 memory({facts['capstone_topic']['value']})")
        if summary:
            hints.append("최근 대화 요약")
        joined = ", ".join(hints)
        return f"질문을 확인했습니다. 현재 답변은 {joined}을 참고해 이어가겠습니다: {user_input}"

    def _fallback_response(self, user_input):
        """Fallback answer when no memory is available."""
        text = str(user_input).strip()
        if text.endswith("?") or "?" in text:
            return f"아직 관련 memory는 없지만 질문의 의도는 확인했습니다. '{text}'에 답하려면 먼저 관련 정보를 알려주세요."
        return f"입력 내용을 확인했습니다. 중요한 정보라면 다음 대화에서 다시 활용할 수 있도록 memory에 저장하겠습니다: {text}"

    def _facts_by_key(self, replayed_memories):
        facts = {}
        for memory in replayed_memories or []:
            if isinstance(memory, dict) and memory.get("type") == "fact":
                facts[memory.get("key")] = memory
        return facts

    def _summary(self, replayed_memories):
        for memory in replayed_memories or []:
            if isinstance(memory, dict) and memory.get("type") == "summary":
                return memory
        return None

    def _extract_value(self, user_input):
        """Extract the likely fact value for acknowledgement text."""
        text = str(user_input).strip()
        patterns = [
            r"내\s*이름은\s*(.+?)(?:이야|야|입니다|이에요|예요|라고\s*해)?[.?!]?$",
            r"나는\s*캡스톤으로\s*(.+?)(?:을|를)?\s*만들고\s*있어[.?!]?$",
            r"내\s*캡스톤\s*주제는\s*(.+?)(?:이야|야|입니다|이에요|예요)?[.?!]?$",
            r"나는\s*(.+?)(?:을|를)?\s*만들고\s*있어[.?!]?$",
            r"내\s*프로젝트는\s*(.+?)(?:이야|야|입니다|이에요|예요)?[.?!]?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._clean(match.group(1))
        return ""

    def _clean(self, value):
        cleaned = str(value).strip()
        cleaned = re.sub(r"[.。!?！？]+$", "", cleaned)
        cleaned = re.sub(r"(이야|야|입니다|이에요|예요|라고 해)$", "", cleaned).strip()
        cleaned = re.sub(r"(을|를)$", "", cleaned).strip()
        return cleaned

    def _particle_eul(self, value):
        """Return 을/를 for a Korean value, using 를 as fallback."""
        return "을" if self._has_jongseong(value) else "를"

    def _particle_ro(self, value):
        """Return 으로/로 for a Korean value, using 로 as fallback."""
        return "으로" if self._has_jongseong(value) else "로"

    def _has_jongseong(self, value):
        """Return True when the last Korean syllable has a final consonant."""
        text = str(value).strip()
        if not text:
            return False
        code = ord(text[-1])
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        return False
