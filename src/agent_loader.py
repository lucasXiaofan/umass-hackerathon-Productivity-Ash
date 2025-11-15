import yaml
from datetime import datetime
from typing import Dict, Any, List

class ContextManager:
    """Manages context gathering and caching"""
    
    def __init__(self, config: dict):
        self.providers = config.get("context_providers", {})
        self.cache = {}
        self.cache_timestamps = {}
    
    def get_context(self, context_names: List[str]) -> Dict[str, str]:
        """Gather requested context, using cache when valid"""
        context = {}
        current_time = datetime.now().timestamp()
        
        for name in context_names:
            if name not in self.providers:
                print(f"⚠️  Unknown context: {name}")
                continue
            
            provider = self.providers[name]
            cache_seconds = provider.get("cache_seconds", 0)
            
            # Check cache
            if name in self.cache:
                cache_age = current_time - self.cache_timestamps[name]
                if cache_age < cache_seconds:
                    context[name] = self.cache[name]
                    continue
            
            # Call provider function
            func_name = provider["function"]
            args = provider.get("args", [])

            try:
                # Import functions dynamically to avoid circular imports
                from tool import get_datetime_context, get_conversation_summary, read_instructions
                from time_depends_tasks import get_tasks_summary
                from agent_log import get_recent_logs

                # Call your actual functions
                if func_name == "get_datetime_context":
                    result = get_datetime_context()
                elif func_name == "get_tasks_summary":
                    result = get_tasks_summary()
                elif func_name == "get_recent_logs":
                    result = get_recent_logs(*args)
                elif func_name == "read_instructions":
                    result = read_instructions()
                elif func_name == "get_conversation_summary":
                    result = get_conversation_summary(*args)
                else:
                    result = f"[Unknown function: {func_name}]"
                
                # Cache result
                self.cache[name] = result
                self.cache_timestamps[name] = current_time
                context[name] = result
                
            except Exception as e:
                print(f"⚠️  Error getting {name}: {e}")
                context[name] = f"[Error: {e}]"
        
        return context


class AgentConfig:
    def __init__(self, config_path="agents.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.context_manager = ContextManager(self.config)
    
    def get_agent(self, name: str) -> dict:
        """Get agent config with context injected into prompt"""
        agent = self.config["agents"][name]
        
        # Gather context
        context_needs = agent.get("context_needs", [])
        context = self.context_manager.get_context(context_needs)
        
        
        # Inject context into prompt using .format()
        try:
            rendered_prompt = agent["prompt"].format(**context)
        except KeyError as e:
            print(f"⚠️  Missing context variable in prompt: {e}")
            rendered_prompt = agent["prompt"]
        
        return {
            "model": self.config["models"][agent["model"]],
            "system_prompt": rendered_prompt,
            "tools": agent.get("tools", []),
            "role": agent.get("role", "")
        }
    
    def list_agents(self) -> dict:
        """Show all agents and their roles"""
        return {
            name: config["role"] 
            for name, config in self.config["agents"].items()
        }
    