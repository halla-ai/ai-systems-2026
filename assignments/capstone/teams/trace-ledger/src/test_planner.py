import json
from core.tools import TraceTools

def test():
    raw_logs = TraceTools.read_raw_log('logs/user_input_history.jsonl')
    if isinstance(raw_logs, str):
        logs_str = raw_logs
    else:
        logs_str = json.dumps(raw_logs, indent=2, ensure_ascii=False)
        
    prompt = f"다음은 개발자가 AI와 나눈 기술적 대화 로그입니다. 분석하여 핵심 원인과 패턴, 설계 의도를 도출하세요:\n\n{logs_str}"
    print("--- PROMPT TO SEND ---")
    print(prompt)

if __name__ == "__main__":
    test()
