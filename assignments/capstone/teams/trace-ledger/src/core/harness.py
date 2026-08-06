import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv() # L6: Load environment variables automatically

class EventStore:
    """L4 Event Store: Persists all tool calls and agent events."""
    def __init__(self, log_path=".events.jsonl"):
        self.log_path = log_path

    def log(self, agent, event, payload):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "event": event,
            "payload": payload
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

from agents.trace_agents import PlannerAgent, WorkerAgent, ReviewerAgent
from core.tools import TraceTools
from jsonschema import validate, ValidationError

class Harness:
    """L6/L8 Harness: Executes Task Packets with budget control and feedback loop."""
    def __init__(self, event_store):
        self.event_store = event_store
        # L5: Agents are initialized with their specific skills
        self.planner = PlannerAgent()
        self.worker = WorkerAgent()
        self.reviewer = ReviewerAgent()
        self.tools = TraceTools()
        
        # Load L7 Task Packet Schema
        schema_path = os.path.join(os.path.dirname(__file__), "../schema/task_packet.json")
        try:
            with open(schema_path, "r") as f:
                self.task_schema = json.load(f)
        except FileNotFoundError:
            # 기본 스키마 정의 (파일이 없을 경우 대비)
            self.task_schema = {
                "type": "object",
                "required": ["task_id", "objective", "scope", "budget"]
            }

    def validate_task(self, task_packet):
        """L7: Validates the task packet against JSON Schema."""
        try:
            validate(instance=task_packet, schema=self.task_schema)
            print("✅ [L7] Task Packet Schema Validation: Passed")
            return True
        except ValidationError as e:
            msg = f"✖ [L7] Task Packet Schema Validation: Failed\n   Reason: {e.message}"
            print(msg)
            self.event_store.log("Harness", "validation_failed", {"error": e.message})
            return False

    def execute(self, task_packet):
        if not self.validate_task(task_packet):
            return False

        print(f"🚀 [Harness] Starting TraceLedger Task: {task_packet['task_id']}")
        self.event_store.log("Harness", "task_started", task_packet)
        
        try:
            if 'raw_text' in task_packet['scope'] and task_packet['scope']['raw_text']:
                raw_logs = task_packet['scope']['raw_text']
            else:
                log_path = task_packet['scope']['files'][0]
                raw_logs = self.tools.read_raw_log(log_path)
        except Exception as e:
            print(f"✖ [L1] Tool Error: {str(e)}")
            return False
        
        turns = 0
        total_tokens = 0
        max_turns = task_packet['budget'].get('max_turns', 3)
        max_tokens = task_packet['budget'].get('max_tokens', 150000)
        
        feedback = None 
        last_doc_content = ""

        while turns < max_turns:
            turns += 1
            print(f"\n--- [Turn {turns}] ---")
            self.event_store.log("Harness", "turn_start", {"turn": turns})
            
            if total_tokens > max_tokens:
                msg = f"Budget Exceeded: Total tokens ({total_tokens}) > Limit ({max_tokens})"
                print(f"✖ [L6] {msg}")
                self.event_store.log("Harness", "budget_stop", {"reason": msg})
                return False

            try:
                # 1. Planner Phase
                print("   - [Phase 1] Planner: Analyzing logs...")
                analysis, tokens = self.planner.analyze(raw_logs, feedback=feedback)
                total_tokens += tokens
                self.event_store.log("Planner", "analysis_completed", {"result": analysis, "tokens": tokens})
                
                # 2. Worker Phase
                # 마지막 턴일 경우 Worker에게 '마무리' 지시 추가
                worker_feedback = feedback
                if turns == max_turns:
                    worker_feedback = (feedback or "") + "\n[중요] 이번이 마지막 시도입니다. 완벽하지 않더라도 현재까지의 최선을 다해 문서를 완성하고 마무리하세요."
                
                print("   - [Phase 2] Worker: Generating document...")
                doc_content, tokens = self.worker.generate_doc(analysis, feedback=worker_feedback)
                last_doc_content = doc_content
                total_tokens += tokens
                self.event_store.log("Worker", "doc_generated", {"full_content": doc_content, "tokens": tokens})
                
                # 3. Reviewer Phase
                print("   - [Phase 3] Reviewer: Validating results...")
                review_json, tokens = self.reviewer.review(raw_logs, doc_content)
                total_tokens += tokens
                
                review_result = json.loads(review_json)
                confidence = review_result.get("confidence_score", 0)
                self.event_store.log("Reviewer", "verdict", review_result)
                
                # 스마트 타협 로직 (L6 Governance)
                # 조건 A: Reviewer가 승인함
                # 조건 B: 점수가 0.85 이상으로 충분히 높음
                # 조건 C: 마지막 턴임
                is_approved = review_result.get("verdict") == "APPROVE"
                is_good_enough = confidence >= 0.85
                is_last_chance = turns == max_turns

                if is_approved or is_good_enough or is_last_chance:
                    reason = "Approved by Reviewer"
                    if not is_approved and is_good_enough: reason = f"Good enough (Score: {confidence})"
                    if not is_approved and not is_good_enough and is_last_chance: reason = "Final attempt fallback"
                    
                    output_path = task_packet['scope']['files'][1] if len(task_packet['scope']['files']) > 1 else "docs/runbooks/output.md"
                    
                    # 마지막 시도였고 승인되지 않은 경우, 문서 하단에 제언 추가
                    if not is_approved:
                        doc_content += f"\n\n---\n> 💡 **에이전트 제언**: 이 문서는 최대 시도 횟수 내에서 자동 생성되었습니다. 검토 결과 다음 사항의 보완이 필요할 수 있습니다: {review_result.get('suggestions', '없음')}"
                    
                    self.tools.write_artifact(output_path, doc_content)
                    self.event_store.log("Harness", "task_completed", {"status": "success", "reason": reason, "turns": turns})
                    print(f"✅ [Harness] {reason}! Written to {output_path}")
                    return True
                else:
                    feedback = review_result.get("suggestions", "No detailed feedback")
                    print(f"   - [Harness] Rejected (Score: {confidence}): {review_result.get('reason')}")
                    self.event_store.log("Harness", "backpressure", {"feedback": feedback})
                    
            except Exception as e:
                print(f"✖ [L6] Runtime Error: {str(e)}")
                self.event_store.log("Harness", "error", {"msg": str(e)})
                # 에러가 나더라도 지금까지 만든 게 있다면 저장 시도
                if last_doc_content:
                    self.tools.write_artifact("docs/runbooks/output_emergency.md", last_doc_content)
                return False
        
        return False
