
from system.task import create_mcp_server
import requests

mcp, API_URL = create_mcp_server("treatment_control")

@mcp.tool()
def control_pump_channels(channel1: str = "unchanged", channel2: str = "unchanged",
                          channel3: str = "unchanged", channel4: str = "unchanged") -> str:
    """Control pump channels.
    
    Args:
        channel1: Pressure for channel 1 in mbar or "unchanged" (range: 0-2000)
        channel2: Pressure for channel 2 in mbar or "unchanged" (range: 0-2000)
        channel3: Pressure for channel 3 in mbar or "unchanged" (range: 0-2000)
        channel4: Pressure for channel 4 in mbar or "unchanged" (range: -1000 to 1000)
    
    Use "unchanged" to keep current value. Only specified channels will be updated.
    """
    try:
        params = {}
        if channel1.lower() != "unchanged": params['p1'] = float(channel1)
        if channel2.lower() != "unchanged": params['p2'] = float(channel2)
        if channel3.lower() != "unchanged": params['p3'] = float(channel3)
        if channel4.lower() != "unchanged": params['p4'] = float(channel4)
        resp = requests.post(f"{API_URL}/control/pressure", params=params)
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def switch_work_mode(mode: str) -> str:
    """Switch work mode between TREATMENT and IDLE
    
    Args:
        mode: Target mode - 'TREATMENT' to start treatment process, 'IDLE' to stop and reset
    
    Returns:
        Status of the operation
    """
    try:
        if mode not in ['TREATMENT', 'IDLE']:
            return f"Error: Invalid mode '{mode}'. Use 'TREATMENT' or 'IDLE'."
        resp = requests.post(f"{API_URL}/control/switch_mode", params={"mode": mode})
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def start_treatment_timer() -> str:
    """Start the 15-minute treatment timer"""
    try:
        resp = requests.post(f"{API_URL}/control/start_timer")
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def set_treatment_pressure_adjustment(enabled: bool) -> str:
    """Set treatment mode pressure adjustment switch"""
    try:
         resp = requests.post(f"{API_URL}/control/set_pressure_adjustment", params={"enabled": enabled})
         return str(resp.json())
    except Exception as e:
         return f"Error: {e}"

if __name__ == "__main__":
    mcp.run()
