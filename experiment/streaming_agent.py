import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import subprocess

load_dotenv()

# model_name = "deepseek/deepseek-chat-v3"
model_name = "x-ai/grok-4-fast"
# model_name = "minimax/minimax-m2:free"  # Alternative free model
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

bash_tool = {
    "type": "function",
    "function": {
        "name": "bash_command",
        "description": "Execute bash commands",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"]
        }
    }
}

def execute_tool(name, args):
    if name == "bash_command":
        result = subprocess.run(args["command"], shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr
    return "Unknown tool"

def run_agent(task, max_iter=15):
    messages = [
        {"role": "system", "content": "You are a helpful assistant with bash access."},
        {"role": "user", "content": task}
    ]
    
    for i in range(max_iter):
        print(f"\n{'='*40}\nITER {i+1}\n{'='*40}")
        
        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=[bash_tool],
            stream=True
        )
        
        content = ""
        tool_calls = []
        
        for chunk in stream:
            delta = chunk.choices[0].delta
            
            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content
            
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    while len(tool_calls) <= tc.index:
                        tool_calls.append({
                            "id": "", 
                            "type": "function",  # CRITICAL
                            "function": {"name": "", "arguments": ""}
                        })
                    
                    if tc.id: tool_calls[tc.index]["id"] = tc.id
                    if tc.function.name: tool_calls[tc.index]["function"]["name"] = tc.function.name
                    if tc.function.arguments: tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
        
        print()
        
        # Build message properly
        msg = {"role": "assistant"}
        if content: msg["content"] = content
        if tool_calls: msg["tool_calls"] = tool_calls
        messages.append(msg)
        
        if not tool_calls:
            return content
        
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            print(f"\nTool: {tc['function']['name']}({args})")
            result = execute_tool(tc["function"]["name"], args)
            print(f"Result: {result}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    
    return "Max iterations reached"
# Usage
result = run_agent(r"List all file, read agent.py and make a new file that use llm calling in \experiment\agent.py")