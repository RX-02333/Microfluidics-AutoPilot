"""
Test Script: Simulate backend sending notification messages to frontend
Uses exactly same code as _send_ui_message in treatment/logic.py

Usage: python test_ui_message.py
Ensure UI server is running on port 8501
"""
import requests
import time

UI_URL = "http://127.0.0.1:8501"

def _send_ui_message(message, msg_type="system", ui_port=8501):
    """Exactly identical to _send_ui_message in logic.py"""
    try:
        url = f"{UI_URL}/ui/add_{msg_type}_message"
        resp = requests.post(url, json={"message": message}, timeout=1)
        print(f"[{msg_type}] Sent: {message} -> {resp.status_code} {resp.json()}")
    except Exception as e:
        print(f"[{msg_type}] Failed: {message} -> {e}")

if __name__ == "__main__":
    print(f"Testing UI message sending to {UI_URL}")
    print("=" * 50)
    
    # Test 1: Send system type message (should display as system notification in frontend)
    print("\n[Test 1] Sending system message...")
    send_ui_message("Troubleshooting triggered", msg_type="system")
    time.sleep(3)
    
    # Test 2: Send another system type message
    print("\n[Test 2] Sending system message...")
    send_ui_message("Troubleshooting completed", msg_type="system")
    time.sleep(3)
    
    # Test 3: Send user type message (should trigger Agent processing and reply)
    print("\n[Test 3] Sending user message (will trigger Agent)...")
    send_ui_message("Qualified gas-liquid interface formed!", msg_type="user")
    time.sleep(3)
    
    # Test 4: Send another user type message
    print("\n[Test 4] Sending user message (will trigger Agent)...")
    send_ui_message("treatment timer complete", msg_type="user")
    
    print("\n" + "=" * 50)
    print("Done! Check the frontend UI for messages.")
