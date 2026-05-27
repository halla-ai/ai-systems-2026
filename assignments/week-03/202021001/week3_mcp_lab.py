"""Week 03 MCP lab stub for 202021001

가벼운 실행용 스텁입니다. 실제 실습에서는 FastMCP 등을 사용합니다.
"""

import json

def get_virtual_mig_status():
    status = {
        "gpu": 0,
        "instances": [
            {"gi": 1, "profile": "1g.5gb", "memory": "5120MiB"},
            {"gi": 2, "profile": "1g.5gb", "memory": "5120MiB"}
        ],
        "note": "This is a virtual MIG status for testing"
    }
    return status

if __name__ == "__main__":
    s = get_virtual_mig_status()
    print(json.dumps(s, indent=2, ensure_ascii=False))
