import os
import json
import re
from openai import OpenAI

class BaseAgent:
    """L2 Provider Completion: Handles LLM calls with instructions and token tracking."""
    def __init__(self, name, instruction_path):
        self.name = name
        base_url = os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=base_url if base_url else None
        )
        # 다시 원래대로 환경변수 LLM_MODEL 하나만 사용하도록 수정
        self.model = os.getenv("LLM_MODEL", "gpt-4o")
        self.total_tokens = 0
        
        with open(instruction_path, "r", encoding="utf-8") as f:
            self.instruction = f.read()

    def preprocess_logs(self, raw_logs):
        """L2: Noise Filtering - 토큰 절감을 위해 불필요한 데이터 제거"""
        if not isinstance(raw_logs, str):
            raw_logs = str(raw_logs)
        processed = re.sub(r'\n\s*\n', '\n', raw_logs)
        ignore_patterns = [
            r"안녕하세요", r"반갑습니다", r"도움이 필요하신가요",
            r"Can I help you with anything else", r"I hope this helps",
            r"어떤 도움이 필요하신가요"
        ]
        for pattern in ignore_patterns:
            processed = re.sub(pattern, "", processed, flags=re.IGNORECASE)
        return processed.strip()

    def chat(self, user_content, response_format=None, feedback=None):
        try:
            user_content = self.preprocess_logs(user_content)
            messages = [{"role": "system", "content": self.instruction}]
            
            if feedback:
                messages.append({"role": "assistant", "content": "이전 작업물에 대한 피드백을 수용합니다."})
                messages.append({"role": "user", "content": f"피드백 반영 요청:\n{feedback}"})

            messages.append({"role": "user", "content": user_content})
            
            args = {"model": self.model, "messages": messages}
            if response_format:
                args["response_format"] = response_format
                
            completion = self.client.chat.completions.create(**args)
            usage = completion.usage
            self.total_tokens += usage.total_tokens
            
            content = completion.choices[0].message.content
            if response_format and response_format.get("type") == "json_object":
                content = self._clean_json_string(content)
                
            return content, usage.total_tokens
        except Exception as e:
            print(f"!!! [API Error] {self.name} ({self.model}): {str(e)}")
            raise e

    def _clean_json_string(self, s):
        s = s.strip()
        if s.startswith("```json"): s = s[7:]
        if s.endswith("```"): s = s[:-3]
        return s.strip()

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Planner", os.path.join(os.path.dirname(__file__), "../prompts/planner.md"))

    def analyze(self, raw_logs, feedback=None):
        prompt = f"다음 로그를 분석하세요:\n\n{raw_logs}"
        return self.chat(prompt, response_format={"type": "json_object"}, feedback=feedback)

class WorkerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Worker", os.path.join(os.path.dirname(__file__), "../prompts/worker.md"))

    def generate_doc(self, analysis_result, feedback=None):
        prompt = f"다음 분석 결과를 마크다운으로 작성하세요:\n\n{analysis_result}"
        return self.chat(prompt, feedback=feedback)

class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Reviewer", os.path.join(os.path.dirname(__file__), "../prompts/reviewer.md"))

    def review(self, raw_logs, generated_doc):
        prompt = f"로그와 문서를 대조하여 검증하세요.\n\n[로그]\n{raw_logs}\n\n[문서]\n{generated_doc}"
        return self.chat(prompt, response_format={"type": "json_object"})
