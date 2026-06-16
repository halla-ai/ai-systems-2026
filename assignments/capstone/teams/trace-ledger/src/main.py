import os
import json
from dotenv import load_dotenv
from core.harness import Harness, EventStore

load_dotenv() # .env 파일에서 환경 변수 로드

def main():
    # Initialize Core Runtime
    event_store = EventStore(".events.jsonl")
    harness = Harness(event_store)

    # [Test 1] L7 Schema Validation Failure Case
    print("\n[Test 1] 스키마 위반 태스크 테스트 (L7 Validation)")
    bad_packet = {
        "task_id": "invalid-001",
        "objective": "Objective only, missing other fields"
    }
    harness.execute(bad_packet)

    # [Test 2] Normal Execution with Feedback Loop and Budgeting
    print("\n[Test 2] 정상 태스크 실행 (L1-L7 Full Pipeline)")
    task_packet = {
        "task_id": "trace-ledger-2026-001",
        "objective": "Analyze debugging history and generate a runbook for Redis timeout.",
        "scope": {
            "files": ["logs/sample_raw_session.txt", "docs/runbooks/jwt_fix.md"]
        },
        "allowed_tools": ["read_raw_log", "write_artifact"],
        "acceptance": [
            "Runbook must include Root Cause and Resolution",
            "Markdown format must pass checking"
        ],
        "budget": {
            "max_turns": 3,
            "max_tokens": 100000
        }
    }
    harness.execute(task_packet)
    
    # [Test 3] General Context Assetization (ADR Generation)
    print("\n[Test 3] 일반 기술 맥락 자산화 테스트 (ADR Generation)")
    adr_packet = {
        "task_id": "trace-ledger-adr-001",
        "objective": "Analyze the real-time communication stack discussion and generate an ADR.",
        "scope": {
            "files": ["logs/architecture_discussion.jsonl", "docs/adr/001-chat-protocol.md"]
        },
        "allowed_tools": ["read_raw_log", "write_artifact"],
        "acceptance": [
            "Must explain why Socket.io was chosen over gRPC",
            "Must mention the Adapter Pattern for future migration"
        ],
        "budget": {
            "max_turns": 3,
            "max_tokens": 100000
        }
    }

    harness.execute(adr_packet)

if __name__ == "__main__":
    main()
