import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

def create_agent_server(agent_instance):
    """Factory to create FastAPI app for a specific agent instance"""
    
    app = FastAPI()

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/chat/stream")
    async def chat_stream(request: Request):
        """Directly forward raw data from agent.run()"""
        data = await request.json()
        history = data.get("history", [])
        
        async def raw_stream():
            try:
                response_generator = agent_instance.run(messages=history)
                
                previous_response = []
                
                for response in response_generator:
                    if isinstance(response, list):
                        # Iterate through current message list
                        for i, msg in enumerate(response):
                            # Convert Message object to dict if needed
                            if hasattr(msg, 'model_dump'):
                                msg_dict = msg.model_dump(exclude_none=True)
                            elif isinstance(msg, dict):
                                msg_dict = msg.copy()
                            else:
                                msg_dict = dict(msg)
                            
                            # If new message (index exceeds previous length)
                            if i >= len(previous_response):
                                yield f"data: {json.dumps(msg_dict)}\n\n"
                                await asyncio.sleep(0.01)
                            # If existing message, check if content changed
                            elif msg_dict != previous_response[i]:
                                yield f"data: {json.dumps(msg_dict)}\n\n"
                                await asyncio.sleep(0.01)
                        
                        # Update cache
                        previous_response = [
                            (m.model_dump(exclude_none=True) if hasattr(m, 'model_dump') else (m.copy() if isinstance(m, dict) else dict(m)))
                            for m in response
                        ]
                        
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_msg = {
                    "role": "assistant", 
                    "content": f"Agent Error: {str(e)}"
                }
                yield f"data: {json.dumps(error_msg)}\n\n"
        
        return StreamingResponse(raw_stream(), media_type="text/event-stream")

    @app.get("/workflow_path")
    async def get_workflow_path():
        """Return the absolute path to workflow.txt in current working directory"""
        import os
        workflow_path = os.path.join(os.getcwd(), "workflow.txt")
        if os.path.exists(workflow_path):
            return {"path": workflow_path, "exists": True}
        else:
            return {"path": None, "exists": False}
        
    return app