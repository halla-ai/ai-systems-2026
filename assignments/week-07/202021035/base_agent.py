import anthropic
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from jsonschema import validate, ValidationError


class BaseAgent(ABC):
    """모든 파이프라인 에이전트의 공통 기반 클래스."""

    def __init__(self, name: str, schema_path: str | None = None):
        self.name = name
        self.client = anthropic.Anthropic()
        self.schema = self._load_schema(schema_path) if schema_path else None
        self.messages: list[dict] = []

    def _load_schema(self, path: str) -> dict:
        return json.loads(Path(path).read_text())

    def _validate_output(self, data: dict) -> bool:
        if self.schema is None:
            return True
        try:
            validate(instance=data, schema=self.schema)
            return True
        except ValidationError as e:
            print(f"[{self.name}] 스키마 검증 실패: {e.message}")
            return False

    def _call(self, system: str, user: str) -> str:
        self.messages.append({"role": "user", "content": user})
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        response = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=self.messages,
        )
        text = response.content[0].text
        self.messages.append({"role": "assistant", "content": text})
        return text

    def _extract_json(self, text: str) -> dict:
        """응답 텍스트에서 JSON 블록을 추출한다."""
        import re
        match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
        if match:
            return json.loads(match.group(1))
        # 코드 블록 없이 순수 JSON인 경우
        return json.loads(text.strip())

    @abstractmethod
    def run(self, input_data: dict) -> dict:
        pass