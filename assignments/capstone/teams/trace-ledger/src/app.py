import os
import json
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from core.harness import Harness, EventStore

# 환경 변수 자동 로드
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

current_task = {"status": "IDLE"}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/start', methods=['POST'])
def start_task():
    global current_task
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    data = request.json
    raw_history = data.get('history')
    objective = data.get('objective', '사용자가 입력한 대화 로그 분석 및 기술 자산화')

    if not raw_history or len(raw_history.strip()) == 0:
        return jsonify({"error": "History is empty after parsing"}), 400

    os.makedirs('logs', exist_ok=True)
    with open('logs/user_input_history.jsonl', 'w', encoding='utf-8') as f:
        f.write(raw_history.strip())

    # 태스크 패킷 설정 (최대 5턴으로 상향)
    task_packet = {
        "task_id": f"trace-interactive-{os.urandom(4).hex()}",
        "objective": objective,
        "scope": {
            "files": ["docs/runbooks/output.md"],
            "raw_text": raw_history.strip()
        },
        "allowed_tools": ["read_raw_log", "write_artifact"],
        "acceptance": ["Must output in Markdown format", "Include Root Cause and Decisions"],
        "budget": {"max_turns": 5, "max_tokens": 150000}
    }

    def run_agent():
        global current_task
        current_task['status'] = 'RUNNING'
        event_store = EventStore(".events.jsonl")
        
        # 로그 초기화
        with open(".events.jsonl", "w") as f: f.write("") 
        
        try:
            harness = Harness(event_store)
            harness.execute(task_packet)
        except Exception as e:
            event_store.log("System", "error", {"msg": str(e)})
            
        current_task['status'] = 'IDLE'

    thread = threading.Thread(target=run_agent)
    thread.start()

    return jsonify({"message": "Task started", "task_id": task_packet['task_id']})

@app.route('/.events.jsonl')
def get_events():
    if os.path.exists('.events.jsonl'):
        return send_from_directory('.', '.events.jsonl')
    return ""

if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    os.makedirs('docs/runbooks', exist_ok=True)
    print("TraceLedger Portal is running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000)
