#!/bin/bash

# 4주차 Ralph 루프 하네스: backpressure, garbage collection, stuck detection, metrics
# 작성자: 202321006

# 환경 변수 초기화
LOOP_LIMIT=5
FAILED_COUNT=0
STUCK_THRESHOLD=2
METRICS_FILE="loop_metrics.json"
LOG_FILE="loop_log.txt"

# 초기 메트릭 파일 생성
echo "[]" > $METRICS_FILE
echo "--- Ralph Loop Started at $(date) ---" > $LOG_FILE

echo "[System] Starting Ralph Loop implementation..."

for ((i=1; i<=LOOP_LIMIT; i++)); do
    START_TIME=$(date +%s)
    echo "[Loop #$i] Executing agent..." | tee -a $LOG_FILE

    # 1. 태스크 실행 (예시: calc.py 코드 생성 요청 시뮬레이션)
    # 실제 환경에서는 여기서 AI 에이전트 CLI를 호출합니다.
    # 여기서는 간단히 실패와 성공 상황을 가정하여 로직을 구성합니다.
    
    # Stuck 탐지 로직 (가산점 항목)
    if [ $FAILED_COUNT -ge $STUCK_THRESHOLD ]; then
        echo "[Stuck Detection] Too many failures. Splitting tasks into smaller units." | tee -a $LOG_FILE
        # 태스크를 더 잘게 쪼개는 로직 (시뮬레이션)
        AGENT_MODE="Simple"
    else
        AGENT_MODE="Full"
    fi

    # 2. Backpressure (테스트 검증)
    if [ -f "test_calc.py" ]; then
        pytest test_calc.py >> $LOG_FILE 2>&1
        TEST_RESULT=$?
    else
        # 초기 단계에서 테스트 파일이 없는 경우 실패로 간주
        TEST_RESULT=1
    fi

    # 3. Garbage Collection 및 결과 처리
    if [ $TEST_RESULT -eq 0 ]; then
        echo "[Success] Test passed on Loop #$i" | tee -a $LOG_FILE
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        # 성공 메트릭 기록
        echo "{\"loop\": $i, \"status\": \"success\", \"duration\": $DURATION}" >> $METRICS_FILE
        break
        else
        echo "[Backpressure] Test failed on Loop #i. Triggering Garbage Collection..." | tee -a $LOG_FILE
        # Garbage Collection: 마지막 성공 상태로 코드 되돌리기
        rm -f calc.py

        FAILED_COUNT=$((FAILED_COUNT + 1))

        # 실패 메트릭 기록 (간단히 누적)
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "{\"loop\": $i, \"status\": \"failed\", \"failed_count\": $FAILED_COUNT, \"duration\": $DURATION}" >> $METRICS_FILE

        
        # AGENTS.md에 실패 내용 기록 (Ralph 루프의 핵심: 누적 학습)
        echo "| #$i | Test failed on loop $i | Need to refine error handling | Ongoing |" >> AGENTS.md
    fi

    if [ $i -eq $LOOP_LIMIT ]; then
        echo "[System] Loop limit reached without success." | tee -a $LOG_FILE
    fi
done

echo "--- Ralph Loop Finished at $(date) ---" >> $LOG_FILE
echo "[System] Metrics saved to $METRICS_FILE"
