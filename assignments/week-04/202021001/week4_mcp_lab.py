"""Week 04 MCP test stub for 202021001
"""

import json


def get_sample_mig_report():
    report = {
        "gpu": 0,
        "timestamp": "2026-05-27T00:00:00Z",
        "instances": [
            {"gi": 1, "profile": "1g.5gb", "memory_used": "1024MiB", "memory_total": "5120MiB"}
        ]
    }
    return report


if __name__ == "__main__":
    print(json.dumps(get_sample_mig_report(), indent=2, ensure_ascii=False))
