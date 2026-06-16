import subprocess
import os
import math
import re
from datetime import datetime

class RiskEvaluator:
    """
    Unified Knowledge Risk Engine (UKRE)
    Uses Information Theory (Entropy) + Temporal Decay + Logic Density
    """
    def __init__(self, repo_path="."):
        self.repo_path = repo_path

    def calculate_entropy(self, author_weights):
        """
        [Information Theory] Measures the imbalance of knowledge distribution using Shannon Entropy.
        - Low value: Knowledge is monopolized by a few (Monopoly).
        - High value: Knowledge is well-distributed among the team.
        """
        total = sum(author_weights.values())
        if total == 0: return 0
        
        entropy = 0
        for weight in author_weights.values():
            p = weight / total
            if p > 0:
                entropy -= p * math.log2(p)
        
        # Max Entropy (Perfect distribution) = log2(number of authors)
        num_authors = len(author_weights)
        if num_authors <= 1:
            return 0
            
        max_entropy = math.log2(num_authors)
        # Normalize to 0~1 (0 = Monopoly, 1 = Distributed)
        return entropy / max_entropy

    def get_temporal_weighted_stats(self, file_path):
        """
        [Temporal Decay] Gives higher weight to recent commits using Exponential Decay.
        Identifies who *currently* holds the most active knowledge.
        """
        try:
            # Get authors and timestamps: author_email|unix_timestamp
            cmd = ["git", "log", "--follow", "--format=%ae|%at", "--", file_path]
            output = subprocess.check_output(cmd, cwd=self.repo_path).decode().splitlines()
            
            if not output: return None
            
            now = datetime.now().timestamp()
            # 180 days half-life (Knowledge decays by 50% every 6 months)
            half_life = 180 * 24 * 60 * 60 
            
            weighted_authors = {}
            for line in output:
                try:
                    email, timestamp = line.split('|')
                    age = now - int(timestamp)
                    # Weight = 0.5 ^ (age / half_life)
                    weight = math.pow(0.5, age / half_life)
                    weighted_authors[email] = weighted_authors.get(email, 0) + weight
                except ValueError:
                    continue
                
            total_weight = sum(weighted_authors.values())
            if total_weight == 0: return None
            
            sorted_authors = sorted(weighted_authors.items(), key=lambda x: x[1], reverse=True)
            top_author, top_weight = sorted_authors[0]
            
            return {
                "top_author": top_author,
                "share": top_weight / total_weight,
                "entropy": self.calculate_entropy(weighted_authors),
                "total_commits": len(output),
                "unique_authors": len(weighted_authors)
            }
        except Exception as e:
            print(f"Temporal stats error for {file_path}: {e}")
            return None

    def calculate_logic_density(self, file_path):
        """
        [Engineering Code Analysis] Measures the density of control flow (Complexity Proxy).
        Identifies code that actually needs an explanation of 'Why'.
        """
        try:
            full_path = os.path.join(self.repo_path, file_path)
            if not os.path.exists(full_path): return 0
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
            
            if not lines: return 0
            
            # Patterns that indicate complex logic/branching
            logic_patterns = [
                r'\bif\b', r'\bfor\b', r'\bwhile\b', r'\bexcept\b', 
                r'\bcase\b', r'\?\.? ', r'\bcatch\b', r'&&', r'\|\|',
                r'\bdef\b', r'\bfunction\b', r'\bclass\b'
            ]
            
            logic_count = sum(len(re.findall(p, content)) for p in logic_patterns)
            
            # Density = Logic Count per 100 lines (Normalized to max 20)
            density = (logic_count / len(lines)) * 100
            return round(min(20, density), 2)
        except Exception as e:
            print(f"Logic density error for {file_path}: {e}")
            return 5

    def evaluate_risk(self, file_path):
        """
        [Unified Risk Score] Calculates 0-100 score.
        Score = (Share * 40%) + ((1-Entropy) * 30%) + ((LogicDensity/20) * 30%)
        """
        stats = self.get_temporal_weighted_stats(file_path)
        if not stats: return None
        
        density = self.calculate_logic_density(file_path)
        
        # 1. Temporal Monopoly Share (40pts)
        share_score = stats['share'] * 40
        
        # 2. Knowledge Imbalance/Monopoly via Entropy (30pts)
        # Low entropy means monopoly. (1-entropy) is our risk factor.
        entropy_score = (1 - stats['entropy']) * 30
        
        # 3. Logic Density (30pts)
        # Density 20+ yields max 30 points.
        density_score = (density / 20) * 30
        
        total_risk = share_score + entropy_score + density_score
        
        stats.update({
            "file": file_path,
            "logic_density": density,
            "risk_score": round(min(100, total_risk), 2)
        })
        return stats

    def evaluate_pr_files(self, files):
        """
        Analyzes PR files and returns prioritized risky files.
        """
        risky_files = []
        for f in files:
            # Filter for meaningful source files
            if not f.lower().endswith(('.py', '.js', '.ts', '.go', '.rs', '.java', '.cpp', '.c', '.cs')):
                continue
            
            risk_stats = self.evaluate_risk(f)
            if risk_stats and risk_stats['risk_score'] > 65 and risk_stats['total_commits'] >= 2:
                risky_files.append(risk_stats)
        
        return sorted(risky_files, key=lambda x: x['risk_score'], reverse=True)

if __name__ == "__main__":
    evaluator = RiskEvaluator()
    # Self-test on a workspace file
    test_file = "package.json" # Not source, but useful for testing logic
    if os.path.exists(test_file):
        print(f"--- UKRE Analysis: {test_file} ---")
        risk = evaluator.evaluate_risk(test_file)
        if risk:
            print(f"Risk Score: {risk['risk_score']}")
            print(f"Temporal Share: {risk['share']:.2f}")
            print(f"Knowledge Entropy: {risk['entropy']:.2f} (0=Monopoly, 1=Distributed)")
            print(f"Logic Density: {risk['logic_density']}")
