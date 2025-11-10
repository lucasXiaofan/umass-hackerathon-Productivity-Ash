"""
ReAct Agent with OpenAI Tool Calling (Mac Version)

Uses proper OpenAI tool calling API instead of text parsing.
Works natively on macOS.

Usage:
    agent = ReActAgent()
    result = agent.run("Read the contents of example.py and create a summary in summary.txt")
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import subprocess

# Load environment variables and configure client
load_dotenv()
# model_name = "deepseek/deepseek-chat-v3"
model_name = "minimax/minimax-m2:free"  # Alternative free model
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Define tools using OpenAI function calling format
bash_tool = {
    "type": "function",
    "function": {
        "name": "bash_command",
        "description": "Execute bash/shell commands on macOS. Can create files, list directories, read files, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
}

think_tool = {
    "type": "function",
    "function": {
        "name": "think",
        "description": "Continue internal reasoning and reflection before giving final answer. Use this to analyze, plan, or reconsider your approach.",
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your internal thoughts, analysis, or reflection"
                }
            },
            "required": ["thought"]
        }
    }
}


def execute_tool(name: str, args: dict) -> str:
    """
    Execute a tool and return the result.
    
    Args:
        name: Tool name
        args: Tool arguments
        
    Returns:
        Tool execution result
    """
    if name == "bash_command":
        try:
            # macOS uses /bin/bash or /bin/zsh by default
            result = subprocess.run(
                args["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                executable='/bin/bash'  # or '/bin/zsh' if preferred
            )
            if result.returncode == 0:
                return f"Success:\n{result.stdout}" if result.stdout else "Success (no output)"
            else:
                return f"Error (code {result.returncode}):\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    elif name == "think":
        # Return acknowledgment, allowing agent to continue reasoning
        return "Thought recorded. Continue thinking or provide final answer."
    return "Unknown tool"


class ReActAgent:
    """ReAct agent using proper OpenAI tool calling API."""
    
    def __init__(self, max_iterations=15, verbose=True, system_message=None):
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.tools = [bash_tool, think_tool]
        self.system_message = system_message or """You are a helpful assistant with access to bash commands on macOS.

Use the bash_command tool to execute shell commands.
Use the think tool when you need to reason about your approach.

When the task is complete, provide a final text response (don't call any tools)."""

    def run(self, task: str) -> str:
        """
        Run the ReAct agent on a task using tool calling.
        
        Args:
            task: The task description
            
        Returns:
            The final answer or result
        """
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": task}
        ]
        
        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"ITERATION {iteration + 1}")
                print(f"{'='*60}")
            
            # Get LLM response with tools
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=self.tools,
                temperature=0
            )
            
            msg = response.choices[0].message
            messages.append(msg)
            
            # Check if assistant made tool calls
            if msg.tool_calls:
                if self.verbose:
                    print(f"Type: TOOL_CALL")
                    print(f"Assistant wants to use {len(msg.tool_calls)} tool(s):")
                
                # Execute each tool
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    if self.verbose:
                        print(f"\n  Tool: {name}")
                        print(f"  Args: {json.dumps(args, indent=8)}")
                    
                    result = execute_tool(name, args)
                    
                    if self.verbose:
                        print(f"  Result: {result}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
            else:
                # Final text response - agent is done
                if self.verbose:
                    print(f"Type: TEXT_RESPONSE")
                    print(f"Content: {msg.content}")
                return msg.content
        
        if self.verbose:
            print(f"\n{'='*60}")
            print("MAX ITERATIONS REACHED")
            print(f"{'='*60}")
        
        return f"[ERROR]: Max iterations ({self.max_iterations}) reached without completing task"


# Example usage
if __name__ == "__main__":
    
    
    # Example 2: Simple file operation
    # result = agent.run(
    #     "Create a file called hello.txt with the content 'Hello from macOS!'"
    # )
    # print(f"\n{'='*60}\nFinal Result:\n{result}\n{'='*60}")