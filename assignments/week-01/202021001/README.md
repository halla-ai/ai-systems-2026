# Week 01 과제 - 202021001

## 제출 정보

- 학번: 202021001
- 과제: Lab 01 - 개발 환경 설정
- 사용한 AI 코딩 CLI: Codex CLI

## 제출 파일

```text
assignments/week-01/202021001/
├── README.md
└── hello_agent.py
```

스크린샷 제출 시 아래 파일명을 같은 폴더에 추가한다.

```text
codex-version.png
dgx-ssh.png
```

## 설치 및 실행 과정

### 1. Node.js와 npm 확인

```bash
node -v
npm -v
```

### 2. Codex CLI 설치

```bash
npm install -g @openai/codex
```

### 3. Codex CLI 버전 확인

```bash
codex --version
```

### 4. Codex CLI로 Python 파일 생성

Codex CLI에 다음 요청을 입력했다.

```text
1주차 과제용으로 간단한 hello_agent.py 파일을 만들어줘.
```

생성된 파일은 `hello_agent.py`이며, 실행 명령은 다음과 같다.

```bash
uv run python hello_agent.py
```

예상 출력:

```text
Hello, AI Systems 2026! Codex CLI generated this message.
```

## 설치 과정에서 겪은 문제와 해결 방법

### 문제 1: npm 전역 설치 권한 문제

- 증상: `npm install -g @openai/codex` 실행 시 권한 오류가 발생할 수 있다.
- 원인: 전역 패키지 설치 경로에 현재 사용자의 쓰기 권한이 없기 때문이다.
- 해결: Node.js를 사용자 권한으로 재설치하거나 npm global prefix를 사용자 홈 디렉터리로 변경한다.

```bash
npm config set prefix ~/.npm-global
```

이후 셸 설정 파일에 PATH를 추가한다.

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
```

### 문제 2: CLI 명령어를 찾지 못하는 문제

- 증상: 설치 후 `codex: command not found`가 표시된다.
- 원인: npm 전역 설치 경로가 PATH에 포함되어 있지 않다.
- 해결: `npm bin -g` 또는 npm prefix 설정을 확인하고 해당 경로를 PATH에 추가한다.

### 문제 3: DGX 서버 SSH 접속 실패

- 증상: `Permission denied (publickey)` 오류가 발생할 수 있다.
- 원인: 공개키가 서버의 `authorized_keys`에 등록되어 있지 않거나 잘못된 계정으로 접속했다.
- 해결: 로컬 공개키를 서버에 등록하고, 접속 계정과 호스트 주소를 다시 확인한다.

```bash
ssh-keygen -t ed25519
ssh-copy-id user@dgx-host
ssh user@dgx-host
```

## AI 시스템 분석 보고서

Codex CLI는 단순한 AI 모델이 아니라 AI 시스템에 가깝다. 내부에는 언어 모델이 있지만, 사용자는 CLI 인터페이스를 통해 파일 읽기, 코드 수정, 명령 실행, 상태 확인 같은 작업 흐름을 수행한다. 7대 구성요소 관점에서는 모델, 도구 사용, 실행 환경, 메모리 또는 컨텍스트, 사용자 인터페이스, 정책 및 권한 제어, 로그 기반 관찰 요소가 결합되어 있다. 따라서 Codex CLI의 핵심 가치는 모델 자체보다 모델을 실제 개발 작업에 연결하는 시스템 구조에서 나온다.

## 실행 결과

```bash
$ uv run python hello_agent.py
Hello, AI Systems 2026! Codex CLI generated this message.
```

## 정리

1주차 과제를 통해 AI 코딩 CLI가 단순히 답변을 생성하는 도구가 아니라, 개발 환경과 파일 시스템, 명령 실행 절차를 연결하는 에이전틱 개발 시스템이라는 점을 확인했다.
