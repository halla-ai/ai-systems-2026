
import subprocess
import json
import os
from datetime import datetime

class RealAgentHarness:
    def __init__(self):
        self.knowledge_file = "KNOWLEDGE.md"
        
    def get_git_monopoly(self):
        print("🔍 [1/3] 실제 Git 커밋 이력 분석 중...")
        # 현재 디렉토리의 파일 목록 가져오기
        files = subprocess.check_output(["git", "ls-files"]).decode().splitlines()
        
        monopoly_report = []
        for f in files:
            if not f.endswith(('.py', '.md', '.js', '.ts')): continue
            
            # 각 파일별 커밋 저자 통계 추출
            try:
                log = subprocess.check_output(["git", "log", "--format=%ae", "--", f]).decode().splitlines()
                if not log: continue
                
                total = len(log)
                authors = {}
                for author in log:
                    authors[author] = authors.get(author, 0) + 1
                
                # 독점도 계산 (최대 지분 보유자의 비율)
                max_author = max(authors, key=authors.get)
                share = authors[max_author] / total
                
                if share > 0.7 and total > 2: # 70% 이상 독점 시
                    monopoly_report.append({"file": f, "author": max_author, "share": share})
            except:
                continue
        
        return sorted(monopoly_report, key=lambda x: x['share'], reverse=True)

    def run_interview(self, target):
        print(f"\n⚠️  [2/3] 지식 독점 감지: {target['file']}")
        print(f"   (보유자: {target['author']}, 독점도: {target['share']*100:.1f}%)")
        print("-" * 50)
        
        # Ralph Loop 시뮬레이션
        while True:
            print(f"\n[Agent] {target['author']}님, {target['file']}의 설계 의도와 핵심 로직을 설명해주세요.")
            answer = input("[You] ")
            
            if len(answer) < 10:
                print("\n[Agent] ✖ 답변이 너무 짧습니다. 다른 팀원이 이해할 수 있도록 구체적인 'Why'를 포함해주세요.")
                continue
            
            if "왜" not in answer and "이유" not in answer and "때문에" not in answer:
                print("\n[Agent] ✖ 설계 '이유(Rationale)'가 누락되었습니다. 어떤 배경에서 이렇게 작성하셨나요?")
                continue
                
            print("\n[Agent] ✔ 고품질 지식 추출 성공!")
            return answer

    def finalize(self, file, author, rationale):
        print("\n📝 [3/3] 지식 영속화 중...")
        content = f"\n## 📌 Module: {file}\n- **Owner**: {author}\n- **Rationale**: {rationale}\n- **Updated**: {datetime.now()}\n"
        
        with open(self.knowledge_file, "a") as f:
            f.write(content)
        
        print(f"✅ {self.knowledge_file}에 기록되었습니다.")

    def start(self):
        report = self.get_git_monopoly()
        if not report:
            print("✅ 현재 프로젝트는 지식이 고르게 분산되어 있습니다.")
            return

        target = report[0] # 가장 심각한 파일 선택
        rationale = self.run_interview(target)
        self.finalize(target['file'], target['author'], rationale)

if __name__ == "__main__":
    harness = RealAgentHarness()
    harness.start()
