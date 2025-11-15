"""
Manager Agent System with Worker Delegation

This script implements a manager/worker agent architecture:
- Manager agent (router) handles user interaction and delegates specialized tasks
- Worker agents (paper_agent, task_agent, session_agent) execute domain-specific work
- Uses YAML config (agents_config.yaml) for agent definitions
- Supports text, image, and voice (TTS) inputs
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from tool import *
from agent_loader import AgentConfig
import re
import warnings
from tts_pipeline import queue_tts

# Suppress warnings
warnings.filterwarnings('ignore')

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Load agent config
agent_config = AgentConfig("src/agents_config.yaml")

def run_worker_agent(agent_name, task_description, max_iter=15):
    """
    Execute a worker agent with a specific task

    Args:
        agent_name: Name of worker agent (paper_agent, task_agent, session_agent)
        task_description: What the worker should do (includes all context from manager)
        max_iter: Maximum tool call iterations

    Returns:
        Final result from worker agent
    """
    print(f"\n{'='*60}")
    print(f"🔧 WORKER: {agent_name}")
    print(f"📋 Task: {task_description}")
    print(f"{'='*60}\n")

    # Get agent config with minimal context (just datetime from YAML)
    agent = agent_config.get_agent(agent_name)

    # Build worker message - simple text only
    user_message = {
        "role": "user",
        "content": [{"type": "text", "text": task_description}]
    }

    messages = [
        {"role": "system", "content": agent["system_prompt"]},
        user_message
    ]

    # Get tool list for this agent
    agent_tools = []
    for tool_name in agent.get("tools", []):
        # Find matching tool definition
        for tool_def in tools:
            if tool_def["function"]["name"] == tool_name:
                agent_tools.append(tool_def)
                break

    print(f"🔨 Worker tools: {[t['function']['name'] for t in agent_tools]}")

    # Execute worker agent loop
    for i in range(max_iter):
        print(f"\n--- Worker Iteration {i+1} ---")

        stream = client.chat.completions.create(
            model=agent["model"],
            messages=messages,
            tools=agent_tools if agent_tools else None,
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
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        })

                    if tc.id: tool_calls[tc.index]["id"] = tc.id
                    if tc.function.name: tool_calls[tc.index]["function"]["name"] = tc.function.name
                    if tc.function.arguments: tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments

        print()

        # Build message
        msg = {"role": "assistant"}
        if content: msg["content"] = content
        if tool_calls: msg["tool_calls"] = tool_calls
        messages.append(msg)

        if not tool_calls:
            print(f"\n✅ Worker {agent_name} completed")
            return content

        # Execute tool calls
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            print(f"\n🔧 Tool: {tc['function']['name']}({args})")
            result = execute_tool(tc["function"]["name"], args)
            print(f"📤 Result: {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })

    return "Worker max iterations reached"


def run_manager_agent(task, image_base64=None, max_iter=15):
    """
    Run manager agent with delegation support

    Args:
        task: User's task/request
        image_base64: Optional screenshot
        max_iter: Maximum iterations

    Returns:
        Final response to user

    Note: Manager handles ALL context (conversation, tasks, logs, instructions).
          When delegating, manager extracts only relevant info for workers.
          Manager can handle simple tasks directly (timers, reminders, file reading).
    """
    print(f"\n{'='*60}")
    print(f"🎯 MANAGER AGENT")
    print(f"{'='*60}\n")

    # Get manager agent config with FULL context injected
    # Context comes from YAML: datetime, tasks, conversation, recent_logs, instructions
    manager = agent_config.get_agent("manager")

    # Build manager message
    user_message = {
        "role": "user",
        "content": [{"type": "text", "text": task}]
    }

    if image_base64:
        user_message["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    messages = [
        {"role": "system", "content": manager["system_prompt"]},
        user_message
    ]

    # Get manager tools
    manager_tools = []
    for tool_name in manager.get("tools", []):
        for tool_def in tools:
            if tool_def["function"]["name"] == tool_name:
                manager_tools.append(tool_def)
                break

    print(f"🔨 Manager tools: {[t['function']['name'] for t in manager_tools]}")

    # Manager execution loop
    for i in range(max_iter):
        print(f"\n{'='*50}")
        print(f"MANAGER ITER {i+1}")
        print(f"{'='*50}")

        stream = client.chat.completions.create(
            model=manager["model"],
            messages=messages,
            tools=manager_tools if manager_tools else None,
            stream=True
        )

        content = ""
        tool_calls = []
        tts_buffer = ""  # For TTS streaming

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content
                tts_buffer += delta.content

                # TTS streaming logic (same as streaming_agent.py)
                sentence_pattern = r'([.!?]+[\s\n]+|[\n]{2,})'
                matches = list(re.finditer(sentence_pattern, tts_buffer))

                if matches:
                    last_match = matches[-1]
                    complete_text = tts_buffer[:last_match.end()].strip()

                    if complete_text and len(complete_text) >= 15:
                        queue_tts(complete_text)
                        tts_buffer = tts_buffer[last_match.end():]
                    elif len(tts_buffer) > 200:
                        queue_tts(tts_buffer.strip())
                        tts_buffer = ""

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    while len(tool_calls) <= tc.index:
                        tool_calls.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        })

                    if tc.id: tool_calls[tc.index]["id"] = tc.id
                    if tc.function.name: tool_calls[tc.index]["function"]["name"] = tc.function.name
                    if tc.function.arguments: tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments

        # Queue remaining TTS
        if tts_buffer.strip():
            queue_tts(tts_buffer.strip())

        print()

        # Build message
        msg = {"role": "assistant"}
        if content: msg["content"] = content
        if tool_calls: msg["tool_calls"] = tool_calls
        messages.append(msg)

        if not tool_calls:
            # Save conversation
            save_conversation(task, msg, "")
            return content

        # Execute tool calls
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            print(f"\n🔧 Manager Tool: {tc['function']['name']}({args})")

            # Check if this is a delegation
            if tc["function"]["name"] == "delegate_to_agent":
                print(f"\n{'='*60}")
                print(f"🚀 DELEGATING TO: {args['agent_name']}")
                print(f"📋 Task: {args['task_description'][:150]}...")
                print(f"{'='*60}")

                # Worker gets simple interface: just agent_name + task_description
                # Manager has already packed all context into task_description
                worker_result = run_worker_agent(
                    agent_name=args["agent_name"],
                    task_description=args["task_description"]
                )

                result = f"Worker {args['agent_name']} completed. Result:\n{worker_result}"
                print(f"\n✅ Worker returned: {result[:200]}...")

            else:
                # Normal tool execution
                result = execute_tool(tc["function"]["name"], args)
                print(f"📤 Result: {result}")

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })

            # Log conversation
            save_conversation(task, {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": f"tool: {tc['function']['name']}, result: {str(result)[:200]}"
            }, "")

    final_result = "Manager max iterations reached"
    save_conversation(task, final_result, "")
    return final_result


def main():
    """Main entry point for testing manager/worker system"""
    print("🎯 Manager/Worker Agent System Ready!")
    print(f"\nAvailable agents: {list(agent_config.list_agents().keys())}")

    print("\nSimple CLI Mode:")
    print("  - Type message: Send text to manager agent")
    print("  - Type 'quit': Exit\n")

    try:
        while True:
            user_input = input("\n💬 You: ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            if user_input.strip():
                # Process through manager (no image support in CLI mode)
                result = run_manager_agent(user_input)
                print(f"\n✅ Done\n")
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
