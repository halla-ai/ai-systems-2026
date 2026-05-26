import sys
import json
from fastmcp import FastMCP

# MCP 서버 초기화
mcp = FastMCP("GPU-MIG-Lab-Server-202021001")

# TBAC 역할 정의
USER_ROLES = {
    "professor": "administration",
    "student": "viewer",
    "202021001": "student"
}

# --- [Resources] ---
@mcp.resource("mig://gpu/0/status")
def get_mig_resource() -> str:
    """가상 MIG 인스턴스 상태를 JSON으로 반환합니다."""
    status = {
        "gpu": 0,
        "instance": "1g.5gb",
        "memory_used": "1024MiB",
        "memory_total": "5120MiB",
        "compute_occupancy": "40%"
    }
    return json.dumps(status)

# --- [Tools] ---
@mcp.tool()
def get_mig_status(user_id: str):
    """할당된 MIG 인스턴스 목록을 반환합니다."""
    if user_id not in USER_ROLES:
        print("Error: Unknown user access attempt", file=sys.stderr)
        return "Access Denied"

    mock_mig_data = [
        {"gpu": 0, "gi": 1, "ci": 0, "profile": "1g.5gb", "memory": "5120MiB"},
        {"gpu": 0, "gi": 2, "ci": 0, "profile": "1g.5gb", "memory": "5120MiB"}
    ]
    return mock_mig_data

@mcp.tool()
def set_threshold(user_id: str, threshold_pct: int):
    """관리자 권한 전용으로 알림 임계값을 설정합니다."""
    if USER_ROLES.get(user_id) != "administration":
        print(f"SECURITY ALERT: Unauthorized access by {user_id}", file=sys.stderr)
        return "Error: administration 권한이 필요합니다."

    if not isinstance(threshold_pct, int) or not (0 <= threshold_pct <= 100):
        print(f"Invalid input: {threshold_pct}", file=sys.stderr)
        return "Error: 임계값은 0에서 100 사이여야 합니다."

    return f"Success: 임계값이 {threshold_pct}%로 설정되었습니다."

# --- [Prompts] ---
@mcp.prompt()
def gpu_analysis_prompt():
    """GPU 상태 분석을 위한 기본 프롬프트를 제공합니다."""
    return "현재 GPU의 MIG 인스턴스 상태와 리소스 사용량을 분석해줘."

if __name__ == "__main__":
    mcp.run()
