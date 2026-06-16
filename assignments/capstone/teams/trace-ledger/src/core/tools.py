import os
import json

class TraceTools:
    """L1 Tool Protocol: Implementation of tools for TraceLedger."""
    
    @staticmethod
    def read_raw_log(file_path):
        """Reads AI-Human chat history and returns as raw text string."""
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found."
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 무조건 텍스트 덩어리 원본으로 반환하여 데이터 유실 원천 차단
        if not content.strip():
            return "Error: File is empty."
            
        return content.strip()

    @staticmethod
    def write_artifact(file_path, content):
        """Writes the generated document to a specific path."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully written to {file_path}"

    @staticmethod
    def validate_markdown(content):
        """Simple linter for markdown (checking headers and code blocks)."""
        issues = []
        if "# " not in content:
            issues.append("Missing H1 header.")
        if "```" not in content:
            issues.append("Missing code blocks for resolution.")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues
        }
