import json
import os
from datetime import datetime

# 1. 실제 오픈소스(예: requests 라이브러리)의 지식 편중 상황 시뮬레이션 데이터
# 특정 모듈(auth.py)을 한 명이 오랫동안 관리한 시나리오
knowledge_graph = {
    "project": "psf/requests",
    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "nodes": [
        {"id": "user:kennethreitz", "name": "Kenneth Reitz", "type": "contributor"},
        {"id": "user:lukasa", "name": "Cory Benfield", "type": "contributor"},
        {"id": "module:requests.auth", "path": "requests/auth.py", "type": "module"}
    ],
    "edges": [
        {
            "from": "user:kennethreitz", 
            "to": "module:requests.auth", 
            "knowledge_score": 0.95, 
            "commit_count": 45,
            "last_interaction": "2026-05-15"
        },
        {
            "from": "user:lukasa", 
            "to": "module:requests.auth", 
            "knowledge_score": 0.05, 
            "commit_count": 2,
            "last_interaction": "2025-11-20"
        }
    ],
    "bus_factor": {
        "requests/auth.py": {"score": 1, "status": "CRITICAL", "owner": "kennethreitz"}
    }
}

# 2. 신규 PR 이벤트 (지식 독점자 Kenneth Reitz가 핵심 로직 수정)
pr_event = {
    "action": "opened",
    "number": 5821,
    "pull_request": {
        "user": {"login": "kennethreitz"},
        "title": "Refactor DigestAuth handling for improved security",
        "changed_files": ["requests/auth.py"],
        "diff_url": "https://github.com/psf/requests/pull/5821.diff"
    }
}

def setup_demo():
    demo_dir = "ai-systems-2026/assignments/week-14/202321006/demo/data"
    
    with open(f"{demo_dir}/knowledge_graph.json", "w") as f:
        json.dump(knowledge_graph, f, indent=2)
        
    with open(f"{demo_dir}/pr_event.json", "w") as f:
        json.dump(pr_event, f, indent=2)
    
    print(f"✅ 데모 데이터 생성 완료: {demo_dir}")

if __name__ == "__main__":
    setup_demo()
