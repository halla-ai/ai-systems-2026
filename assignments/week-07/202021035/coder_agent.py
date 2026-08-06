import os
import subprocess
from base_agent import BaseAgent


# AI 코딩 CLI 도구별 명령어 매핑
TOOL_COMMANDS = {
    "claude": ["claude", "--print", "--no-color", "--dangerously-skip-permissions"],
    "gemini": ["gemini"],       # pipe 모드 사용
    "codex": ["codex", "--approval-mode", "full-auto"],
}


CODER_SYSTEM = """
You are a coding agent. You receive a task plan and implement the code changes.
After making changes, run the specified test command to verify.

Output a JSON object matching the CoderOutput schema.
"""


class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Coder",
            schema_path="schemas/coder_output.json"
        )
        self.ai_cli = os.environ.get("AI_CLI", "claude")

    def run(self, input_data: dict) -> dict:
        plan = input_data["plan"]
        coder_tasks = [
            t for t in plan["subtasks"] if t["assignee"] == "coder"
        ]

        user_prompt = f"""
Task ID: {plan['task_id']}
Objective: {plan['objective']}

Your subtasks:
{chr(10).join(f"- {t['description']}" for t in coder_tasks)}

Constraints:
- Max iterations: {plan['constraints'].get('max_iterations', 5)}
- Forbidden packages: {plan['constraints'].get('forbidden_packages', [])}

Implement the changes and report what you did.
"""
        response_text = self._call(CODER_SYSTEM, user_prompt)

        # AI 코딩 CLI를 헤드리스로 실행해 실제 코드 변경 수행
        cmd = TOOL_COMMANDS.get(self.ai_cli, TOOL_COMMANDS["claude"])
        result = subprocess.run(
            cmd + [response_text],
            capture_output=True, text=True, timeout=300
        )

        return {
            "task_id": plan["task_id"],
            "changes": [],        # 실제로는 git diff 파싱
            "test_command": "pytest tests/ -q",
            "status": "complete" if result.returncode == 0 else "partial",
            "agent_output": result.stdout[:500]
        }