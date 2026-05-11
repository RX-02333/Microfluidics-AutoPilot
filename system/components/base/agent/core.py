
import json
from qwen_agent.agents import Assistant

class Agent:
    def __init__(self, llm_cfg: dict, system_message: str = "You are a helpful assistant.", tools: list = None):
        if tools is None:
            tools = []
            
        self.llm_cfg = llm_cfg
        self.system_message = system_message
        self.tools = tools
        self.bot = None
        
        try:
            self.bot = Assistant(
                llm=self.llm_cfg,
                system_message=self.system_message,
                function_list=self.tools, 
            )
            print("Qwen Agent initialized successfully.")
        except Exception as e:
            print(f"Warning: Failed to init actual Qwen Agent ({e}). Using Mock.")
            self.bot = MockBot()

    def add_system_message(self, message):
        if hasattr(self.bot, 'system_message'):
             self.bot.system_message = message
        else:
             print("Warning: dynamic system message not fully supported in this wrapper version.")

    def run(self, messages):
        try:
            response_generator = self.bot.run(messages=messages)
            for response in response_generator:
                yield response
        except Exception as e:
             yield [{"role": "assistant", "content": f"Agent Error: {e}"}]

class MockBot:
    def run(self, messages, **kwargs):
        yield [{"role": "assistant", "content": "Mock Response: Qwen Agent init failed. Check dependencies."}]
