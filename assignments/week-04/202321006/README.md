# Lab 04: Ralph 루프 구현 및 Test-time Compute Scaling

## 1. 프로젝트 개요
에이전트가 실패를 통해 스스로 학습하고 코드를 수정해 나가는 'Ralph 루프' 하네스를 구현했습니다. `backpressure`(테스트 기반 피드백)와 `garbage collection`(실패 코드 폐기) 메커니즘을 통해 안정적인 자동 코딩 환경을 구축하는 것이 목표입니다.

## 2. 설계 결정 사항
- **Backpressure**: `pytest`의 종료 코드를 활용하여 코드의 유효성을 즉각적으로 판별합니다.
- **Garbage Collection**: 테스트 실패 시 `git checkout` 또는 파일 삭제를 통해 작업 트리를 마지막 성공 상태(Clean state)로 복구합니다.
- **Stuck 탐지 (Extra Credit)**: 동일한 태스크에서 연속 실패(2회 이상) 시, 에이전트에게 더 단순한 구현 방식을 요구하거나 태스크를 분할하도록 유도합니다.
- **루프 메트릭 (Extra Credit)**: 각 루프의 성공 여부, 소요 시간, 실패 횟수를 `loop_metrics.json`에 저장하여 시스템의 효율성을 분석합니다.

## 3. 이론적 배경: Test-time Compute Scaling
Test-time compute scaling은 추론 시 더 많은 계산 자원(루프, 재시도, 검증)을 투입하여 결과의 품질을 높이는 전략입니다. 본 실습의 Ralph 루프는 에이전트가 단일 시도(Single-shot)로 문제를 해결하는 대신, 여러 번의 루프와 자기 수정을 거치며 정답에 수렴하게 함으로써 이 이론을 실천합니다.

## 4. 실행 방법
```bash
chmod +x harness.sh
./harness.sh
```
