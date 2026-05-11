
from system.task import create_mcp_server
import requests

mcp, API_URL = create_mcp_server("liposome_control")

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
def liposome_create_process() -> str:
    """Execute liposome generation process"""
    try:
        resp = requests.post(f"{API_URL}/control/start_generation")
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def reset_to_idle() -> str:
    """Reset system to idle state"""
    try:
        resp = requests.post(f"{API_URL}/control/stop")
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def liposome_size_adjustment(action: str, target_size: str = "0") -> str:
    """Start or stop liposome size adjustment mode.
    
    Args:
        action: "start" to begin adjustment, "stop" to end it
        target_size: Target liposome size in um (e.g. "15.0"), only needed when action is "start"
    
    Use this when: User wants to adjust liposome size to a specific target, or stop an ongoing adjustment.
    The system automatically adjusts P1 pressure every 120 frames with ±2 mbar steps until |diff| <= 0.2 um.
    """
    try:
        if action.lower() == "start":
            resp = requests.post(f"{API_URL}/control/size_adjustment", params={"action": "start", "target_size": float(target_size)})
        elif action.lower() == "stop":
            resp = requests.post(f"{API_URL}/control/size_adjustment", params={"action": "stop"})
        else:
            return f"Error: Invalid action '{action}'. Use 'start' or 'stop'."
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    mcp.run()
