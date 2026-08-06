## PR 제목

[제출] Lab 06 - 202021035 홍길동

## 제출 내용

- `log_analyzer.py` 구현  
  - `harness.log`를 읽어 오류 패턴을 추출  
  - `syntax`, `logic`, `timeout`, `api`, `other` 카테고리로 분류  
  - 분석 결과를 JSON 파일로 저장하는 기능 포함  
- `error_report.md` 작성  
  - 로그 분석 결과 요약 및 반복 오류 정리  
- `prompt_v1.md`, `prompt_v2.md` 작성  
  - v1: 기본 프롬프트  
  - v2: 로그 분석을 반영해 개선한 프롬프트  
- `ab_test.py` 구현  
  - 두 프롬프트를 비교 실행하고 결과를 수집  
- `ab_results.json` 제출  
  - 실제 A/B 테스트 결과 첨부  
- `README.md` 작성  
  - 실험 결과 분석 및 v2 개선 사항 설명  

## 실행 결과

- `python log_analyzer.py harness.log --json-output categorized.json` 실행 완료  
- `python ab_test.py --run-count 3 --output ab_results.json` 실행 완료  
- `ab_results.json` 생성 및 `README.md`에 분석 요약  

### A/B 테스트 요약 (예시)

| Variant | 성공 여부 | Iterations | 실행 시간 |
|---|---:|---:|---:|
| v1 | 실패 | 2회 | 0.50s |
| v2 | 성공 | 1회 | 0.50s |

### 분석 요약

v2 프롬프트는 오류 분류 및 수정 계획을 문서화하는 지침을 추가함으로써, 반복 오류를 줄이고 테스트 통과율을 높였습니다. v1은 기본적인 지시만 포함되어 있어 루프에 갇힐 위험이 있었습니다.

## PR 전 확인 사항

- [ ] `pnpm run build` 성공  
- [ ] 마크다운 문법 오류 없음  
- [ ] 한국어 맞춤법 검토 완료  
- [ ] 이미지/링크 경로 정상 동작 확인  
- [ ] 제출 경로 확인: `assignments/lab-06/202021035/`  
- [ ] 자기 학번 폴더만 수정  
- [ ] `src/content/docs/`에 과제 파일을 넣지 않음  
- [ ] 한글 파일명 사용하지 않음  
- [ ] `.pyc`, `__pycache__/` 파일 제외  
- [ ] `git diff --stat origin/main`으로 변경 파일 목록 확인  
