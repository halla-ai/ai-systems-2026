import sys
import random
from typing import Optional, Dict, Any
from fastmcp import FastMCP

# Initialize FastMCP
mcp = FastMCP(
    "mig-monitor-202321006",
    description="MIG Slice Status Monitoring & Management Server (Week 03 Assignment)"
)

# --- SAFE PYNVML INITIALIZATION ---
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    print("[WARN] pynvml not found. Using mock data for demonstration.", file=sys.stderr)
    HAS_PYNVML = False

def get_nvml_data(gpu_index: int = 0) -> Dict[str, Any]:
    """Helper to get actual or mock NVML data safely."""
    if not HAS_PYNVML:
        # Simulate realistic MIG 1g.10gb slice data
        return {
            "name": "NVIDIA H100 80GB HBM3 (MIG 1g.10gb)",
            "memory_used_mb": random.randint(1024, 8192),
            "memory_total_mb": 10240,
            "gpu_utilization_pct": random.randint(0, 100),
            "temperature_c": random.randint(40, 65),
            "power_usage_w": random.randint(20, 50)
        }
    
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        name = pynvml.nvmlDeviceGetName(handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0 # mW to W
        pynvml.nvmlShutdown()
        
        return {
            "name": name,
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_total_mb": memory.total // (1024 * 1024),
            "gpu_utilization_pct": util.gpu,
            "temperature_c": temp,
            "power_usage_w": power
        }
    except Exception as e:
        print(f"[ERROR] NVML Access Failed: {e}", file=sys.stderr)
        return {"error": str(e)}

# --- TOOLS ---

@mcp.tool()
def get_mig_status(gpu_id: int = 0) -> Dict[str, Any]:
    """Returns current GPU/Memory utilization for a specific MIG slice.
    
    Args:
        gpu_id: The index of the GPU to query (0-7).
    """
    # Input Validation
    if not (0 <= gpu_id < 8):
        return {"status": "error", "message": "Invalid GPU ID. Must be 0-7."}
        
    data = get_nvml_data(gpu_id)
    if "error" in data:
        return {"status": "error", "message": data["error"]}
        
    return {
        "gpu_id": gpu_id,
        "model": data["name"],
        "memory_used_mb": data["memory_used_mb"],
        "memory_total_mb": data["memory_total_mb"],
        "utilization_pct": data["gpu_utilization_pct"],
        "status": "healthy" if data["gpu_utilization_pct"] < 90 else "high_load"
    }

@mcp.tool()
def check_memory_pressure(threshold_pct: float = 80.0, gpu_id: int = 0) -> Dict[str, Any]:
    """Checks if memory usage exceeds a specified threshold.
    
    Args:
        threshold_pct: Warning threshold (0.0-100.0).
        gpu_id: GPU index to check.
    """
    # Input Validation
    if not (0.0 <= threshold_pct <= 100.0):
        print(f"[ERROR] Invalid threshold: {threshold_pct}", file=sys.stderr)
        return {"status": "error", "message": "threshold_pct must be between 0.0 and 100.0"}
    
    status = get_mig_status(gpu_id)
    if status["status"] == "error":
        return status
        
    used_pct = (status["memory_used_mb"] / status["memory_total_mb"]) * 100
    return {
        "gpu_id": gpu_id,
        "used_pct": round(used_pct, 2),
        "threshold_pct": threshold_pct,
        "alert": used_pct > threshold_pct,
        "recommendation": "Consider clearing cache or optimizing batch size" if used_pct > threshold_pct else "Status normal"
    }

# --- RESOURCES ---

@mcp.resource("mig://gpu/{gpu_id}/status")
def gpu_status_resource(gpu_id: str) -> str:
    """Provides a human-readable summary of GPU status."""
    try:
        idx = int(gpu_id)
    except ValueError:
        return f"Error: Invalid GPU ID '{gpu_id}'. Must be an integer."
        
    status = get_mig_status(idx)
    if status["status"] == "error":
        return f"Error: {status['message']}"
        
    return (
        f"--- MIG GPU {idx} Status ---\n"
        f"Model: {status['model']}\n"
        f"Memory: {status['memory_used_mb']} / {status['memory_total_mb']} MB\n"
        f"Utilization: {status['utilization_pct']}%"
    )

@mcp.resource("mig://gpu/{gpu_id}/metrics")
def gpu_metrics_resource(gpu_id: str) -> str:
    """BONUS: Provides real-time metrics (Temp, Power, etc.) for monitoring."""
    try:
        idx = int(gpu_id)
    except ValueError:
        return f"Error: Invalid GPU ID '{gpu_id}'."
        
    data = get_nvml_data(idx)
    if "error" in data:
        return f"Error: {data['error']}"
        
    return (
        f"--- Real-time Metrics (GPU {idx}) ---\n"
        f"Temperature: {data['temperature_c']}°C\n"
        f"Power Usage: {data['power_usage_w']}W\n"
        f"Memory Used: {data['memory_used_mb']}MB\n"
        f"GPU Load: {data['gpu_utilization_pct']}%"
    )

# --- PROMPTS ---

@mcp.prompt()
def gpu_analysis_prompt(student_id: str = "202321006") -> str:
    """Prompt template for analyzing GPU health and resource allocation."""
    return (
        f"Hello, this is a request for GPU resource analysis from student {student_id}.\n\n"
        "Please analyze the current MIG slice health based on the following criteria:\n"
        "1. Is the memory usage near the 10GB limit?\n"
        "2. Are there frequent spikes in GPU utilization?\n"
        "3. Based on the temperature and power usage, is the hardware throttling?\n"
        "4. Suggest any necessary adjustments to the MIG profile if the current workload is high."
    )

if __name__ == "__main__":
    mcp.run()
