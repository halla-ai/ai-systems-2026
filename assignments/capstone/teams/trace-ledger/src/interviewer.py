import os
import json
from openai import OpenAI

class Interviewer:
    """
    Handles the Ralph Loop interview process using OpenAI API.
    Supports 'Zero-Draft' to lower developer friction.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def analyze_response(self, question, response):
        """
        Uses OpenAI (GPT-4o) to determine if the developer's response is satisfactory.
        """
        if not self.client:
            return self._mock_llm_logic(question, response)

        prompt = f"""
        당신은 'Nudge Agent'라는 이름의 시니어 소프트웨어 아키텍트입니다.
        PR 작성자로부터 고품질의 '설계 의도(Why)'를 추출하는 것이 목표입니다.

        [상황]
        질문: "{question}"
        개발자의 답변: "{response}"

        [판단 기준]
        1. 답변이 단순히 "수정했다"는 사실 나열인가, 아니면 "왜"라는 이유를 포함하는가?
        2. 다른 팀원이 유지보수할 때 실질적인 도움이 되는 맥락인가?
        
        응답 형식 (JSON):
        {{
            "verdict": "ACCEPT" or "REJECT",
            "feedback": "한국어 피드백 메시지"
        }}
        """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            result = json.loads(completion.choices[0].message.content)
            return result.get("verdict") == "ACCEPT", result.get("feedback")
        except:
            return self._mock_llm_logic(question, response)

    def generate_zero_draft_question(self, file_stats, diff_content=None):
        """
        [Zero-Draft] Analyzes code changes and suggests a hypothetical rationale.
        Includes an Internal Loop (Critic) to refine the question quality.
        """
        author = file_stats['top_author'].split('@')[0]
        filename = file_stats['file']
        risk = file_stats['risk_score']

        if not self.client or not diff_content:
            return self.generate_initial_question(file_stats)

        prompt = f"""
        당신은 시니어 아키텍트입니다. 아래 코드 변경점(diff)을 분석하여 개발자의 '설계 의도'를 추측해보세요.
        파일: {filename}
        변경점:
        {diff_content[:2000]} 

        응답 형식 (JSON):
        {{
            "hypothesis": "코드를 분석해보니 ~를 위해 ~한 방식으로 구현하신 것으로 보입니다. 맞을까요?",
            "technical_point": "특히 ~한 부분이 인상적인데, 이 방식의 장점은 무엇인가요?"
        }}
        """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            draft = json.loads(completion.choices[0].message.content)
            
            raw_question = f"""
👋 안녕하세요 @{author}님! **Nudge Agent**입니다.

분석 결과 `{filename}`은 현재 기술적 복잡도가 높고 지식 집중도가 높아(위험도: {risk}점), 설계 공유가 권장됩니다.

**[Zero-Draft: 제가 분석한 내용입니다]**
> {draft['hypothesis']}
> {draft['technical_point']}

위 내용이 맞는지 확인해 주시거나, 추가적인 설계 의도가 있다면 짧게 공유 부탁드립니다! 🚀
"""
            # [Internal Loop: Critic]
            is_valid, refined_question = self._verify_question_quality(raw_question, filename)
            return refined_question if is_valid else raw_question

        except Exception as e:
            print(f"Zero-draft error: {e}")
            return self.generate_initial_question(file_stats)

    def _verify_question_quality(self, question, filename):
        """
        [Inner Loop] Critics the generated question for tone and technical relevance.
        """
        if not self.client:
            return True, question

        prompt = f"""
        당신은 'Nudge Agent'의 품질 검증관(Critic)입니다. 
        생성된 인터뷰 질문이 다음 기준을 만족하는지 검사하세요.
        
        [기준]
        1. 어조: 개발자를 존중하고 협력을 유도하는가? (공격적이지 않은가?)
        2. 구체성: 해당 파일({filename})의 맥락이 잘 녹아있는가?
        3. 간결성: 너무 길지 않고 핵심만 묻는가?

        [질문]
        {question}

        응답 형식 (JSON):
        {{
            "is_valid": true or false,
            "refined_question": "필요시 수정된 질문 내용",
            "reason": "검증 결과 사유"
        }}
        """
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "질문 품질 검증관"}, {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            result = json.loads(completion.choices[0].message.content)
            return result.get("is_valid", True), result.get("refined_question", question)
        except:
            return True, question

    def generate_initial_question(self, file_stats):
        author = file_stats['top_author'].split('@')[0]
        filename = file_stats['file']
        risk = file_stats['risk_score']
        return f"""
👋 안녕하세요 @{author}님! **Nudge Agent**입니다.
분석 결과 `{filename}`의 지식 집중도가 높아(위험도: {risk}점), 짧은 설계 맥락 공유를 부탁드립니다.
- 이 로직의 핵심 **설계 의도(Why)**는 무엇인가요?
- 리뷰어가 주의 깊게 봐야 할 **잠재적 리스크**가 있을까요?
"""

    def _mock_llm_logic(self, question, response):
        if len(response.split()) < 8:
            return False, "답변이 조금 짧네요! 조금만 더 자세히 적어주세요. 😊"
        return True, "훌륭한 설명 감사합니다! ✨"
