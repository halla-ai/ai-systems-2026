# 설치 과정에서 겪은 문제와 해결 방법

(서버 접속 + AI CLI 설치 과정에서 겪은 문제와 해결을 아래에 적습니다.)

## 문제 1: SSH 접속 시 Permission denied (publickey)
- **증상**: DGX 서버 접속 시 비밀번호 입력 없이 `Permission denied`만 반복됨.
- **해결**: `ssh-keygen`으로 키 생성 후 `ssh-copy-id user@host`로 공개키 등록. 또는 서버의 `~/.ssh/authorized_keys`에 로컬 `id_rsa.pub` 내용 추가.

## 문제 2: AI CLI 설치 후 명령어 인식 안 됨
- **증상**: `claude` 또는 `cursor` CLI 설치했는데 터미널에서 `command not found`.
- **해결**: PATH에 안 들어가 있는 경우. `~/.local/bin` 또는 설치 경로를 `~/.bashrc` / `~/.zshrc`의 `export PATH="$PATH:$HOME/.local/bin"` 등으로 추가 후 `source` 또는 재접속.

---
