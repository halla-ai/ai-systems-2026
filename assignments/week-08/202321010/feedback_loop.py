"""피드백 루프: QA 실패 시 Coder 재실행 태스크 생성"""
import json
from pathlib import Path


def enqueue_fix_task(review_result):
    """QA 실패 시 task_queue에 수정 태스크 추가"""
    queue_path = Path("task_queue.json")

    if queue_path.exists():
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    else:
        queue = []

    # 기존 FIX 태스크 개수 확인
    fix_count = sum(1 for t in queue if t["id"].startswith("FIX-QA-"))
    
    task = {
        "id": f"FIX-QA-{fix_count + 1}",
        "type": "fix_qa_failure",
        "priority": "HIGH",
        "status": "pending",
        "feedback_for_coder": review_result["review"]["feedback_for_coder"],
        "issues": review_result["review"].get("issues", []),
        "critical_issues": review_result["review"].get("critical_issues", []),
        "test_output": review_result["test_result"]["stdout"]
    }

    queue.append(task)

    queue_path.write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"  → task_queue에 {task['id']} 추가 완료")
