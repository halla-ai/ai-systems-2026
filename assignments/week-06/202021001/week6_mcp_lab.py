"""Week 06 MCP log analysis stub for 202021001
"""

import json


def parse_dummy_log():
    # 예시 로그 파싱 결과 반환
    return {
        "events": [
            {"time": "2026-05-27T01:00:00Z", "event": "mig_create", "gi": 1},
            {"time": "2026-05-27T01:05:00Z", "event": "mig_alloc", "gi": 1}
        ]
    }

if __name__ == "__main__":
    print(json.dumps(parse_dummy_log(), indent=2, ensure_ascii=False))
