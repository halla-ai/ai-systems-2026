# AGENTS.md: Ralph 루프 누적 학습 기록

## 학습 패턴 기록
| 루프 # | 실패 원인 (Failure Pattern) | 학습 내용 (Learning) | 개선 결과 |
| :--- | :--- | :--- | :--- |
| #1 | 예시: ZeroDivisionError 미처리 | `divide` 함수에 0 체크 로직 추가 필요 | 성공 예상 |
| #2 | 예시: 타입 불일치 | 입력 인자에 대한 정수/실수 타입 가드 강화 | 성공 예상 |

## 누적 가이드라인
- 에러 발생 시 로그를 상세히 분석하여 이 파일에 기록할 것.
- 하네스는 이 파일을 참조하여 다음 루프의 성능을 개선함.
| #1 | Test failed on loop 1 | Need to refine error handling | Ongoing |
| #2 | Test failed on loop 2 | Need to refine error handling | Ongoing |
| #3 | Test failed on loop 3 | Need to refine error handling | Ongoing |
| #4 | Test failed on loop 4 | Need to refine error handling | Ongoing |
| #5 | Test failed on loop 5 | Need to refine error handling | Ongoing |
| #1 | Test failed on loop 1 | Need to refine error handling | Ongoing |
| #2 | Test failed on loop 2 | Need to refine error handling | Ongoing |
| #3 | Test failed on loop 3 | Need to refine error handling | Ongoing |
| #4 | Test failed on loop 4 | Need to refine error handling | Ongoing |
| #5 | Test failed on loop 5 | Need to refine error handling | Ongoing |
