
import subprocess
import os
from datetime import datetime

class SmartAgentHarness:
    def __init__(self):
        self.target_file = "assignments/week-01/game.py" # 예시 파일

    def analyze_code_intent(self, file_path):
        print(f"🧠 [1/4] 에이전트가 {file_path} 코드를 분석 중입니다...")
        with open(file_path, "r") as f:
            content = f.read()
        
        # 실제로는 LLM이 분석하겠지만, 여기서는 논리적 추론 시뮬레이션
        intent_hypothesis = ""
        if "random" in content:
            intent_hypothesis = "사용자에게 매번 새로운 경험(무작위성)을 제공하기 위한 설계"
        elif "loop" in content:
            intent_hypothesis = "지속적인 게임 플레이 흐름을 유지하기 위한 설계"
        else:
            intent_hypothesis = "기본적인 로직 구현"
            
        return intent_hypothesis

    def run_smart_interview(self, file_path, hypothesis):
        print(f"⚠️  [2/4] 지식 공백 발견: 코드는 읽히지만 '비즈니스 의도'가 불분명합니다.")
        print("-" * 60)
        print(f"  [에이전트 가설]: \"이 코드는 '{hypothesis}'를 위해 작성된 것으로 보입니다.\"")
        
        while True:
            print(f"\n[Agent] 제 분석이 맞나요? 아니면 제가 놓친 '진짜 이유'가 있나요?")
            answer = input("[You] ")
            
            if "아니" in answer or "틀려" in answer:
                print("\n[Agent] 💡 아, 제 분석이 틀렸군요! 정확한 의도를 알려주시면 코드를 수정하겠습니다.")
                continue
            
            if len(answer) < 5:
                print("\n[Agent] ✖ 지식이 너무 얕습니다. 후임자가 이 코드를 유지보수할 수 있게 조금만 더 자세히 알려주세요.")
                continue
            
            print("\n[Agent] ✔ 최종 Rationale 확정 및 학습 완료!")
            return answer

    def inject_comment_to_code(self, file_path, rationale):
        print(f"\n📝 [3/4] 소스 코드에 지식 자율 주입 중...")
        
        with open(file_path, "r") as f:
            lines = f.readlines()
            
        # 파일 최상단에 에이전트가 추출한 Rationale 주석 삽입
        comment = f'"""\n[Agentic Rationale]\n{rationale}\nLast Verified: {datetime.now()}\n"""\n'
        lines.insert(0, comment)
        
        with open(file_path, "w") as f:
            f.writelines(lines)
        
        print(f"✅ {file_path} 상단에 설계 의도가 주석으로 기록되었습니다.")

    def start(self):
        # 1. 분석
        hypothesis = self.analyze_code_intent(self.target_file)
        # 2. 인터뷰 (가설 검증)
        final_rationale = self.run_smart_interview(self.target_file, hypothesis)
        # 3. 주석 주입 (실행 결과의 영속화)
        self.inject_comment_to_code(self.target_file, final_rationale)
        print("\n🚀 [4/4] Closed-loop 완료: 인간의 의도가 코드에 물리적으로 결합되었습니다.")

if __name__ == "__main__":
    harness = SmartAgentHarness()
    harness.start()
