"""Week 05 MCP report stub for 202021001
"""

import json
import random


def generate_mig_report():
    instances = []
    for gi in range(1,3):
        memory_total = 5120
        memory_used = random.randint(512, 4096)
        instances.append({
            "gi": gi,
            "profile": "1g.5gb",
            "memory_used_mib": memory_used,
            "memory_total_mib": memory_total,
            "util_pct": round(memory_used / memory_total * 100, 1)
        })
    return {
        "gpu": 0,
        "instances": instances
    }

if __name__ == "__main__":
    report = generate_mig_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
