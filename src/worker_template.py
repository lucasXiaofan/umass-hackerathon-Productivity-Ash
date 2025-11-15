"""
Worker Agent Template and Documentation

This file explains how to create new worker agents for the manager/worker system.
All worker agents are defined in agents_config.yaml and executed by manager_agent.py.

================================================================================
QUICK START: Adding a New Worker Agent
================================================================================

Step 1: Choose your worker's specialty
    - What domain-specific task will this worker handle?
    - Examples: email management, code review, data analysis, calendar scheduling

Step 2: Define tools your worker needs
    - Add to tool_groups in agents_config.yaml if it's a new category
    - Or use existing tool groups: knowledge, tasks, papers, conversation

Step 3: Add worker definition to agents_config.yaml
    - Follow the template below

Step 4: Update delegate_to_agent tool enum in tool.py
    - Add your new worker name to the enum list

================================================================================
WORKER AGENT YAML TEMPLATE
================================================================================

IMPORTANT: Workers should be MINIMAL and FOCUSED.
Manager handles ALL context - workers get only what they need.

Add this to agents_config.yaml under the "agents:" section:

```yaml
  your_worker_name:
    model: multi_smart_1  # or multi_fast_1 for simple tasks

    role: "Brief description of what this worker does"

    # MINIMAL context - manager already has full picture
    context_needs:
      - datetime      # Usually all you need

    tools_from_groups:
      - knowledge     # [update_instructions, log_activity]
      - tasks         # [create_task, update_task]
      - papers        # [brave_search, bash_command]
      - conversation  # [ask_user_question]

    prompt: |
      You are a [worker specialty] specialist.

      The manager has assigned you a specific task.
      Focus ONLY on the task given - don't worry about conversation history.

      Your workflow:
      1. [First step of the workflow]
      2. [Second step of the workflow]
      3. [Third step of the workflow]
      4. Use log_activity when done

      Current time: {datetime}

      Be thorough and systematic.
```

KEY PRINCIPLE: Manager passes relevant info in task_description.
Workers don't need tasks, recent_logs, conversation - manager already checked those!

================================================================================
EXAMPLE 1: Email Worker Agent
================================================================================

```yaml
  email_agent:
    model: multi_smart_1
    role: "Email management specialist"

    # Minimal - manager handles user preferences
    context_needs:
      - datetime

    tools_from_groups:
      - knowledge
      - conversation

    # You'd need to add an email tool group:
    # tool_groups:
    #   email: [send_email, read_inbox, draft_email]

    prompt: |
      You manage emails.

      The manager has given you a specific email task.
      Focus on executing it - manager already checked preferences.

      Workflow:
      1. Read or draft email as requested
      2. Ask user for confirmation before sending
      3. Send if confirmed
      4. Log activity

      Current time: {datetime}

      Always confirm before sending.
```

Manager would delegate like:
```python
delegate_to_agent(
    agent_name="email_agent",
    task_description="Draft a reply to John's email about the meeting. User prefers formal tone.",
    extra_context="Meeting is scheduled for next Tuesday at 2pm"
)
```

================================================================================
EXAMPLE 2: Code Review Worker Agent
================================================================================

```yaml
  code_review_agent:
    model: multi_smart_1
    role: "Code review and analysis specialist"

    # Minimal - manager provides file paths
    context_needs:
      - datetime

    tools_from_groups:
      - papers      # Uses bash_command for git/code operations
      - knowledge   # For logging
      - conversation

    prompt: |
      You perform code reviews.

      The manager has given you specific files to review.
      Focus on those files - manager already checked what needs review.

      Workflow:
      1. Use bash_command to examine the code files
      2. Check for: bugs, security issues, style violations
      3. Search online (brave_search) for best practices if needed
      4. Provide detailed review comments
      5. Log findings with log_activity

      Current time: {datetime}

      Be thorough and constructive.
```

Manager would delegate like:
```python
delegate_to_agent(
    agent_name="code_review_agent",
    task_description="Review the authentication code in src/auth.py for security issues",
    extra_context="User is concerned about SQL injection and password hashing"
)
```

================================================================================
EXAMPLE 3: Data Analysis Worker Agent
================================================================================

```yaml
  data_agent:
    model: multi_smart_2  # Using more capable model
    role: "Data analysis and visualization specialist"

    # Minimal - manager provides data file path
    context_needs:
      - datetime

    tools_from_groups:
      - papers       # bash_command for Python/pandas scripts
      - knowledge
      - conversation
      - tasks        # Can create tasks for follow-up analysis

    prompt: |
      You analyze data and create visualizations.

      The manager has given you a specific dataset to analyze.
      Focus on the analysis requested.

      Workflow:
      1. Use bash_command to run Python analysis scripts
      2. Generate summary statistics and insights
      3. Create visualization files
      4. Create task reminder if further analysis needed
      5. Log what was done

      Current time: {datetime}

      Explain findings clearly and suggest next steps.
```

Manager would delegate like:
```python
delegate_to_agent(
    agent_name="data_agent",
    task_description="Analyze sales data in data/sales_q4.csv. Focus on regional trends and top products.",
    extra_context="User wants to prepare for quarterly review meeting on Nov 20"
)
```

================================================================================
CREATING CUSTOM TOOLS FOR YOUR WORKER
================================================================================

If your worker needs tools not in the current tool_groups, add them to tool.py:

1. Define the tool in the `tools` list (src/tool.py lines 39-223):

```python
{
    "type": "function",
    "function": {
        "name": "your_custom_tool",
        "description": "Clear description of what this tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "What this parameter does"
                },
                "param2": {
                    "type": "integer",
                    "description": "Another parameter"
                }
            },
            "required": ["param1"]
        }
    }
}
```

2. Add execution logic in execute_tool() (src/tool.py line 306+):

```python
elif name == "your_custom_tool":
    # Your implementation here
    result = do_something(args["param1"], args.get("param2", default_value))
    return str(result)
```

3. Add to tool_groups in agents_config.yaml:

```yaml
tool_groups:
  your_category: [your_custom_tool, other_related_tool]
```

4. Reference in your worker's tools_from_groups:

```yaml
  your_worker:
    tools_from_groups: [your_category, knowledge]
```

================================================================================
TESTING YOUR WORKER
================================================================================

1. Start the manager agent:
   ```bash
   cd src
   python manager_agent.py
   ```

2. Test delegation:
   ```
   You: "Can you help me with [task that requires your worker]?"
   ```

3. The manager should recognize the need and delegate:
   ```
   🚀 DELEGATING TO: your_worker_name
   ```

4. Check logs:
   - Conversation history: /memory/conversation_history.json
   - Activity log: /memory/agent_activity.log
   - Tasks created: /memory/tasks.json

================================================================================
BEST PRACTICES
================================================================================

1. **Clear Workflow Steps**
   - Number each step in the prompt
   - Be specific about tool usage
   - Include error handling instructions

2. **Context Management**
   - Only request context you actually need
   - Datetime and recent_logs are usually helpful
   - Instructions are good for user preferences

3. **Tool Selection**
   - Choose the right model for complexity
     * multi_fast_1: Quick, simple tasks
     * multi_smart_1: Complex reasoning
     * multi_smart_2: Needs latest capabilities

4. **Logging**
   - Always end with log_activity
   - Include files_changed parameter when modifying files
   - Use descriptive summaries

5. **User Interaction**
   - Use ask_user_question for confirmations
   - Don't make destructive changes without asking
   - Provide clear status updates

================================================================================
DELEGATION FLOW
================================================================================

User Input
    ↓
Manager Agent (router)
    ├─ Loads FULL context (conversation, tasks, logs, instructions)
    ├─ Analyzes request with complete picture
    ├─ Checks if work already done (recent_logs)
    ├─ Checks user preferences (instructions)
    ├─ Decides: handle directly OR delegate
    ↓
If delegating:
    ├─ EXTRACTS relevant info from conversation
    ├─ SUMMARIZES context into task_description
    ├─ Adds extra_context if needed
    ├─ Calls delegate_to_agent(agent_name, task_description, extra_context)
    ↓
Worker Agent Execution
    ├─ Loads minimal config from YAML (just datetime)
    ├─ Gets focused task_description from manager
    ├─ NO access to conversation, tasks, logs
    ├─ Executes with specialized tools
    ├─ Returns result
    ↓
Manager receives result
    ├─ Has full context to interpret result
    ├─ Summarizes for user
    ├─ Saves conversation
    └─ Ready for next interaction

KEY INSIGHT:
┌─────────────────────────────────────────────────┐
│ Manager = Heavy context, decision making        │
│ Workers = Light context, focused execution      │
│                                                 │
│ Manager has: conversation, tasks, logs, etc.   │
│ Worker gets: "Track paper 'Attention is All    │
│              You Need'" + datetime              │
└─────────────────────────────────────────────────┘

This design:
✓ Reduces worker token costs
✓ Makes workers reusable and simple
✓ Centralizes context management
✓ Prevents repeat work (manager checks logs)

================================================================================
TROUBLESHOOTING
================================================================================

**Worker not being delegated to:**
- Check if agent name is in delegate_to_agent enum (tool.py)
- Ensure manager's prompt mentions this worker capability
- Manager needs clear signals about when to delegate

**Worker can't access tools:**
- Verify tool names match exactly in tools list
- Check tool_groups mapping in agents_config.yaml
- Ensure tools_from_groups references correct groups

**Context not appearing in prompt:**
- Check context_needs list in agent definition
- Verify context provider is defined in agents_config.yaml
- Check agent_loader.py has the function imported

**Worker loops infinitely:**
- Add clear termination condition in prompt
- Include max_iter parameter (default 15)
- Make sure worker knows when task is complete

================================================================================
ADVANCED: Multi-Step Workers with State
================================================================================

For complex workflows that need to track state across steps:

1. Use bash_command to write state files:
   ```python
   # In your worker's prompt:
   "1. Save progress to /memory/worker_state.json using bash_command"
   ```

2. Load state in subsequent steps:
   ```python
   "2. Check /memory/worker_state.json to see where you left off"
   ```

3. Use create_task for follow-up work:
   ```python
   "3. If work is incomplete, create task for continuation"
   ```

================================================================================
QUESTIONS?
================================================================================

See existing workers in agents_config.yaml:
- paper_agent: Complex 6-step workflow with search, file creation, tasks
- task_agent: Simple task management
- session_agent: Activity tracking

The paper_agent is the best example of a complete worker implementation.

Happy building! 🚀
"""
