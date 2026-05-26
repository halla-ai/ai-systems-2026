# Week 02 과제 - 202021001

## 제출 정보

- 학번: 202021001
- 과제: Week 02 MCP / GPU 실습
- 제출 폴더: `assignments/week-02/202021001`

## 제출 파일

```text
assignments/week-02/202021001/
├── README.md
└── mcp_gpu_lab.py
```

## 과제 요약

- RTX 3060은 실제 MIG 기능을 지원하지 않기 때문에, 실습 환경에서는 `nvidia-smi mig -lgi` 명령이 작동하지 않습니다.
- 이를 해결하기 위해 FastMCP 기반 가상 MCP 서버를 만들고, 가상의 MIG 리소스와 도구를 구현했습니다.
- TBAC 역할 기반 접근 제어와 입력 검증도 포함하여 안전한 시뮬레이션 서버를 작성했습니다.

## 설치 및 실행

### 1. Python 패키지 설치

```bash
pip install fastmcp
```

### 2. 파일 실행

```bash
python assignments/week-02/202021001/mcp_gpu_lab.py
```

### 3. Inspector로 체크리스트 확인 (선택)

```bash
npx @modelcontextprotocol/inspector python assignments/week-02/202021001/mcp_gpu_lab.py
```

## 구현 설명

- `FastMCP`를 사용하여 MCP 서버를 초기화했습니다.
- `mig://gpu/0/status` 리소스는 가상 MIG 인스턴스 메모리 정보를 JSON으로 반환합니다.
- `get_mig_status` 도구는 사용자 역할 검증을 수행하고, 정상적인 MIG 인스턴스 목록을 반환합니다.
- `set_threshold` 도구는 administration 권한을 가진 사용자만 호출 가능하며, 임계값 입력 검증을 포함합니다.

## 실행 결과 예시

```bash
$ python assignments/week-02/202021001/mcp_gpu_lab.py
```

실행 시 FastMCP 서버가 시작되며, Inspector나 MCP 클라이언트를 통해 리소스와 도구 호출을 확인할 수 있습니다.

## 문제 해결 접근

- 문제: GPU 하드웨어가 MIG를 지원하지 않아 실습에 필요한 `nvidia-smi mig -lgi`를 실행할 수 없음.
- 해결: 실습 서버 내부에서 가상 MIG 상태를 생성하고, 이를 통해 MCP 검사 항목을 충족하는 시뮬레이션 환경을 구성했습니다.

## 정리

이번 과제는 AI 시스템 실습에서 하드웨어 제약을 소프트웨어 추상화로 해결하는 방법을 보여줍니다. 실제 GPU 대신 가상 MIG 데이터를 사용하면, 모델 컨텍스트 프로토콜 기반 검사와 권한 제어를 함께 테스트할 수 있습니다.
