from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import sys

app = FastAPI(title="Governed MCP Gateway (TBAC Proxy)")

# --- TBAC POLICY DATABASE ---
# Tasks -> Role -> Allowed Tools
TBAC_POLICIES = {
    "monitoring": {
        "student": ["get_mig_status", "check_memory_pressure"],
        "ta": ["get_mig_status", "check_memory_pressure", "get_all_metrics"],
        "admin": ["*"]
    },
    "maintenance": {
        "student": [],
        "ta": ["reset_gpu_slice"],
        "admin": ["*"]
    }
}

class ToolCallRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: Dict[str, Any]
    user_role: str
    task_context: str

@app.post("/proxy/tools/call")
async def governed_tool_call(request: ToolCallRequest):
    """
    Intercepts an MCP tool call and validates it against TBAC policies.
    """
    # 1. Identity & Context Verification
    policy = TBAC_POLICIES.get(request.task_context)
    if not policy:
        raise HTTPException(status_code=403, detail=f"Unknown task context: {request.task_context}")
    
    allowed_tools = policy.get(request.user_role, [])
    
    # 2. Authorization Check (TBAC)
    if "*" not in allowed_tools and request.tool_name not in allowed_tools:
        print(f"[AUDIT] Unauthorized access attempt: {request.user_role} tried {request.tool_name} during {request.task_context}", file=sys.stderr)
        raise HTTPException(
            status_code=403, 
            detail=f"Role '{request.user_role}' is not authorized to use tool '{request.tool_name}' for task '{request.task_context}'"
        )
    
    # 3. Data Leakage Prevention (DLP) - Simple check on arguments
    # Example: Prevent students from querying GPU IDs outside their range (simulated)
    if request.user_role == "student" and request.arguments.get("gpu_id", 0) > 0:
        raise HTTPException(status_code=400, detail="Students can only access their assigned GPU slice (ID 0)")

    # 4. Success - In a real scenario, this would forward to the actual MCP server
    print(f"[AUDIT] Authorized: {request.user_role} calling {request.tool_name}", file=sys.stderr)
    return {
        "status": "authorized",
        "forwarded_to": request.server_name,
        "result": "Success (Mocked response from backend server)"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
