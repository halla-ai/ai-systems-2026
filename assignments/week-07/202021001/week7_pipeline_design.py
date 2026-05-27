"""Week 07 pipeline design stub for 202021001
"""


def describe_pipeline():
    return {
        "stages": ["collect", "analyze", "report"],
        "notes": "Simple example pipeline for MCP monitoring"
    }

if __name__ == "__main__":
    import json
    print(json.dumps(describe_pipeline(), indent=2, ensure_ascii=False))
