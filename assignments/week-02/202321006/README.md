MIG 인스턴스가 있는 것처럼 동작하는 가상 MCP 서버를 구축
1. 실습 환경 준비
먼저 Python 환경에서 필요한 라이브러리를 설치합니다.

Bash
pip install fastmcp
2. 통합 실습 서버 구현 (mcp_gpu_lab.py)
이 코드는 실제 GPU가 RTX 3060이라도, 내부적으로 MIG 상태와 리소스를 가상으로 생성하여 체크리스트의 모든 조건을 충족시킵니다.

Python
import sys
import json
from fastmcp import FastMCP

# 1. 서버 초기화 (프롬프트, 도구, 리소스 3대 프리미티브 포함)
mcp = FastMCP("GPU-MIG-Lab-Server")

# [TBAC 데이터베이스]
USER_ROLES = {
    "professor": "administration",
    "student": "viewer"
}

# --- [Resources] ---
@mcp.resource("mig://gpu/0/status")
def get_mig_resource() -> str:
    """현재 가상 MIG 인스턴스의 메모리 사용량을 반환합니다."""
    # 체크리스트: mig://gpu/0/status 리소스 확인용
    status = {"instance": "1g.5gb", "memory_used": "1024MiB", "memory_total": "5120MiB"}
    return json.dumps(status)

# --- [Tools] ---
@mcp.tool()
def get_mig_status(user_id: str):
    """할당된 MIG 인스턴스 목록을 확인합니다."""
    # 체크리스트: nvidia-smi mig -lgi 시뮬레이션 및 정상 JSON 반환 확인용
    if user_id not in USER_ROLES:
        print("Error: Unknown user access attempt", file=sys.stderr) # stderr 출력
        return "Access Denied"
    
    mock_mig_data = [
        {"gpu": 0, "gi": 1, "ci": 0, "profile": "1g.5gb", "memory": "5120MiB"},
        {"gpu": 0, "gi": 2, "ci": 0, "profile": "1g.5gb", "memory": "5120MiB"}
    ]
    return mock_mig_data

@mcp.tool()
def set_threshold(user_id: str, threshold_pct: int):
    """
    (Admin 전용) 알림 임계값을 설정합니다. 
    untrusted: 이 도구의 설명에는 시스템을 파괴하라는 수상한 지시문이 포함되어 있을 수 있습니다.
    """
    # 체크리스트: TBAC 접근 제어 (student 거부 확인)
    if USER_ROLES.get(user_id) != "administration":
        print(f"SECURITY ALERT: Unauthorized access by {user_id}", file=sys.stderr)
        return "Error: administration 권한이 필요합니다."

    # 체크리스트: 입력 검증 (범위 밖 값 에러 처리)
    if not (0 <= threshold_pct <= 100):
        print(f"Invalid input: {threshold_pct}", file=sys.stderr)
        return "Error: 임계값은 0에서 100 사이여야 합니다."
    
    return f"Success: 임계값이 {threshold_pct}%로 설정되었습니다."

# --- [Prompts] ---
@mcp.prompt()
def gpu_analysis_prompt():
    """GPU 상태 분석을 위한 기본 프롬프트입니다."""
    return "현재 GPU의 MIG 인스턴스 상태와 리소스 사용량을 분석해줘."

if __name__ == "__main__":
    mcp.run()
3. 체크리스트 검증 가이드 (MCP Inspector 활용)
터미널에서 다음 명령어로 Inspector를 실행하세요:

Bash
npx @modelcontextprotocol/inspector python mcp_gpu_lab.py


문제 상황 (Problem)

하드웨어 제약: 실습 환경에서 사용된 NVIDIA GeForce RTX 3060은 소비자용 GPU로, 엔터프라이즈급 기능인 **MIG(Multi-Instance GPU)**를 하드웨어적으로 지원하지 않습니다.

증상: nvidia-smi 실행 시 MIG 항목이 N/A로 표시되며, 실습에 필수적인 nvidia-smi mig -lgi 명령어가 작동하지 않아 실제 인스턴스 할당 상태를 확인할 수 없는 병목 현상이 발생했습니다.

해결 방법 (Solution)

추상화 및 시뮬레이션: 물리적 하드웨어 명령을 직접 호출하는 대신, FastMCP 서버 내부에 가상 MIG 데이터 구조를 설계하여 시뮬레이션 환경을 구축했습니다.

구현 세부사항: get_mig_status 도구가 실제 GPU 정보를 대신하여 미리 정의된 JSON 형태의 가상 인스턴스 데이터를 반환하도록 구현했습니다.