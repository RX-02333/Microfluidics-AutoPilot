
from fastmcp import FastMCP
import requests
import argparse
import sys


def create_mcp_server(name: str = "task_tools"):
    """
    Standard initialization for MCP Server.
    
    Returns:
        (mcp, API_URL): FastMCP instance and API URL
        
    Usage:
        mcp, API_URL = create_mcp_server("my_task_tools")
        
        @mcp.tool()
        def my_tool(...) -> str:
            resp = requests.post(f"{API_URL}/control/my_action", ...)
            return str(resp.json())
        
        if __name__ == "__main__":
            mcp.run()
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', type=str, default='http://localhost:8002')
    args = parser.parse_args()
    
    api_url = args.api_url
    print(f"[MCP {name}] API URL: {api_url}", file=sys.stderr)
    
    mcp = FastMCP(name)
    return mcp, api_url


# ----- Tool templates below. Define specific tools in each Task's mcp_server.py -----
# def make_pressure_tool(mcp, api_url):
#     """
#     Registers a common pump pressure control tool (shareable across multiple Tasks).
#     """
#     @mcp.tool()
#     def control_pump_channels(channel1: str = "unchanged", channel2: str = "unchanged",
#                               channel3: str = "unchanged", channel4: str = "unchanged") -> str:
#         """Control pump channels."""
#         try:
#             params = {}
#             for key, val in [('p1', channel1), ('p2', channel2), ('p3', channel3), ('p4', channel4)]:
#                 if val.lower() != "unchanged":
#                     params[key] = float(val)
#             resp = requests.post(f"{api_url}/control/pressure", params=params)
#             return str(resp.json())
#         except Exception as e:
#             return f"Error: {e}"
