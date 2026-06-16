import os
import json
import unittest
from unittest.mock import MagicMock, patch
from interviewer import Interviewer
from evaluator import RiskEvaluator
from main import NudgeAgent

class TestNudgeAgentLogic(unittest.TestCase):
    def setUp(self):
        # Mock API Key to avoid actual LLM calls if needed, 
        # but here we want to test the 'Internal Loop' logic flow.
        self.interviewer = Interviewer(api_key="mock-key")
        
    def test_inner_loop_logic(self):
        """
        [Inner Loop Test] Checks if _verify_question_quality is called and works.
        """
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # First call for hypothesis, second for refinement (Critic)
        mock_response.choices[0].message.content = json.dumps({
            "hypothesis": "Test hypothesis",
            "technical_point": "Test point"
        })
        
        mock_critic_response = MagicMock()
        mock_critic_response.choices = [MagicMock()]
        mock_critic_response.choices[0].message.content = json.dumps({
            "is_valid": True,
            "refined_question": "Refined: Hello developer, why did you change this?",
            "reason": "Tone is good"
        })

        with patch('openai.resources.chat.completions.Completions.create') as mock_create:
            mock_create.side_effect = [mock_response, mock_critic_response]
            
            file_stats = {"top_author": "junseo", "file": "core.py", "risk_score": 85}
            question = self.interviewer.generate_zero_draft_question(file_stats, "diff content")
            
            self.assertIn("Refined:", question)
            print("\n✅ Inner Loop (Critic) Test Passed: Question refined successfully.")

    def test_metrics_logging(self):
        """
        [Metrics Test] Checks if turn_count and yield are logged in .events.jsonl.
        """
        agent = NudgeAgent(repo_owner_repo="test/repo", pr_number=123)
        event_file = ".test_events.jsonl"
        agent.event_log = event_file
        
        if os.path.exists(event_file): os.remove(event_file)
        
        agent.log_event("GateKeeper", "success", {"file": "test.py", "turns": 3, "extraction_yield": 1.5})
        
        with open(event_file, "r") as f:
            log = json.loads(f.readline())
            self.assertEqual(log["payload"]["turns"], 3)
            self.assertEqual(log["payload"]["extraction_yield"], 1.5)
            
        os.remove(event_file)
        print("✅ Metrics Logging Test Passed: turns and yield correctly recorded.")

if __name__ == "__main__":
    unittest.main()
