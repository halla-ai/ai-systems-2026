import os
import sys
import json
import requests
from datetime import datetime
from interviewer import Interviewer

def run_real_world_simulation(repo="psf/requests", pr_number=7505):
    """
    Simulates Nudge Agent analysis using a real-world PR from a famous repo.
    """
    interviewer = Interviewer()
    print(f"--- Simulating Analysis for {repo} PR #{pr_number} ---")
    
    # 1. Fetch PR details from GitHub API (Public)
    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    files_url = f"{pr_url}/files"
    
    try:
        pr_data = requests.get(pr_url).json()
        files_data = requests.get(files_url).json()
        
        author = pr_data['user']['login']
        title = pr_data['title']
        print(f"PR Title: {title} by @{author}")
        
        # 2. Mocking the RiskEvaluator results (since we don't have local git history for psf/requests)
        # In real usage, this would be calculated by evaluator.py
        mock_risky_files = []
        for f in files_data:
            filename = f['filename']
            if filename.endswith('.py'):
                mock_risky_files.append({
                    "file": filename,
                    "top_author": "kennethreitz", # Simulation: owner of requests
                    "entropy": 0.15,               # Simulation: high monopoly
                    "risk_score": 88.5,
                    "diff": f.get('patch', '')
                })
        
        # 3. Generate Nudge Interview (Zero-Draft) using Interviewer
        event_logs = []
        kg_data = []
        
        for file_stats in mock_risky_files:
            print(f"\n[Interviewer] Analyzing {file_stats['file']}...")
            
            # Generate the Zero-Draft question (Internal Loop happens inside)
            question = interviewer.generate_zero_draft_question(file_stats, file_stats['diff'])
            
            # Log the event
            event = {
                "timestamp": datetime.now().isoformat(),
                "agent": "Interviewer",
                "event": "post_initial_question",
                "payload": {
                    "file": file_stats['file'],
                    "msg": "Zero-Draft generated for real PR content.",
                    "preview": question[:100] + "..."
                }
            }
            event_logs.append(event)
            
            # Update Knowledge Graph data
            file_stats['last_updated'] = datetime.now().isoformat()
            kg_data.append(file_stats)
            
            print(f"Generated Question:\n{question}")

        # 4. Save to files for dashboard
        with open("knowledge_graph.json", "w") as f:
            json.dump(kg_data, f, indent=2)
        
        with open(".events.jsonl", "w") as f:
            for e in event_logs:
                f.write(json.dumps(e) + "\n")
        
        print("\n✅ Simulation Complete. Dashboard data updated with real PR info.")
        print("Open 'index.html' to see the Trace Replay!")

    except Exception as e:
        print(f"Simulation failed: {e}")

if __name__ == "__main__":
    run_real_world_simulation()
