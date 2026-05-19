from base_agent import BaseAgent
import uuid


PLANNER_SYSTEM = """
You are a software planning agent. Your job is to decompose a user request
into a structured plan that other agents can execute.

Output ONLY a valid JSON object matching the PlannerOutput schema.
Do not include any explanation outside the JSON block.
"""


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Planner",
            schema_path="schemas/planner_output.json"
        )

    def run(self, input_data: dict) -> dict:
        objective = input_data["objective"]
        codebase_summary = input_data.get("codebase_summary", "")

        user_prompt = f"""
Objective: {objective}

Codebase context:
{codebase_summary}

Create a task plan. Use task_id format "task-XXXX".
Assign subtasks to: researcher, coder, qa, reviewer.
"""
        response_text = self._call(PLANNER_SYSTEM, user_prompt)

        try:
            plan = self._extract_json(response_text)
        except Exception as e:
            print(f"[Planner] JSON 파싱 실패: {e}")
            # 폴백 플랜
            plan = {
                "task_id": f"task-{uuid.uuid4().hex[:4]}",
                "objective": objective,
                "subtasks": [
                    {
                        "id": "st-01",
                        "description": objective,
                        "assignee": "coder",
                        "depends_on": []
                    }
                ],
                "constraints": {"max_iterations": 5, "forbidden_packages": [], "target_files": []}
            }

        if self._validate_output(plan):
            print(f"[Planner] 계획 생성 완료: {len(plan['subtasks'])}개 서브태스크")
        return plan