"""Model Selector - Intelligent LLM model selection for cost optimization.

This module provides tiered model selection based on task complexity,
choosing the cheapest model that can handle the job effectively.

Cost tiers (relative):
- gemini-2.0-flash-lite: $ (cheapest, simple tasks)
- gemini-2.0-flash: $$ (balanced, general tasks)  
- gemini-2.5-flash: $$$ (vision tasks)
- gemini-2.5-computer-use: $$$$ (browser control only)
"""
from enum import Enum
from typing import Optional


class TaskType(str, Enum):
    """Types of tasks with different LLM requirements."""
    SUMMARIZE = "summarize"           # Text summarization
    DECOMPOSE = "decompose"           # Goal decomposition
    DESCRIBE_IMAGE = "describe_image" # Image description
    BROWSER_CONTROL = "browser"       # Full browser control
    GENERAL_CHAT = "chat"             # General conversation
    EMBED = "embed"                   # Embedding generation


class ModelSelector:
    """
    Select the most cost-effective model for each task type.
    
    Strategy:
    - Use the cheapest model that can handle the task
    - Preserve quality for critical operations (browser control)
    - Log selections for monitoring cost savings
    """
    
    # Model configurations with costs (relative)
    MODELS = {
        "lite": {
            "name": "gemini-2.0-flash-lite",
            "cost": 1,
            "capabilities": ["text", "simple_reasoning"],
            "max_output_tokens": 2048
        },
        "flash": {
            "name": "gemini-2.0-flash",
            "cost": 2,
            "capabilities": ["text", "reasoning", "structured_output"],
            "max_output_tokens": 8192
        },

        "computer_use": {
            "name": "gemini-2.5-computer-use-preview-10-2025",
            "cost": 10,
            "capabilities": ["text", "vision", "browser_control", "computer_use"],
            "max_output_tokens": 16384
        },
        "embedding": {
            "name": "gemini-embedding-001",
            "cost": 0.1,
            "capabilities": ["embedding"],
            "max_output_tokens": 0
        }
    }
    
    # Task to model mapping (cheapest viable option)
    TASK_MODEL_MAP = {
        TaskType.SUMMARIZE: "lite",      # Simple text task
        TaskType.DECOMPOSE: "lite",      # Simple text task
        TaskType.DESCRIBE_IMAGE: "flash", # Upgraded to flash 2.0 (multimodal)
        TaskType.BROWSER_CONTROL: "computer_use",
        TaskType.GENERAL_CHAT: "flash",
        TaskType.EMBED: "embedding"
    }
    
    @classmethod
    def get_model(cls, task_type: TaskType, 
                  needs_vision: bool = False,
                  needs_structured_output: bool = False) -> str:
        """
        Get the optimal model name for a task.
        
        Args:
            task_type: The type of task being performed
            needs_vision: Whether the task requires image understanding
            needs_structured_output: Whether JSON output is required
        
        Returns:
            The model name string to use
        """
        # Get default model tier for this task
        model_tier = cls.TASK_MODEL_MAP.get(task_type, "flash")
        

        
        # Upgrade if structured output is required and using lite
        if needs_structured_output and model_tier == "lite":
            model_tier = "flash"
        
        model_info = cls.MODELS[model_tier]
        model_name = model_info["name"]
        
        print(f"[MODEL] Selected '{model_name}' for {task_type.value} task (cost tier: {model_tier})")
        return model_name
    
    @classmethod
    def get_model_config(cls, task_type: TaskType) -> dict:
        """Get full model configuration for a task."""
        model_tier = cls.TASK_MODEL_MAP.get(task_type, "flash")
        return cls.MODELS[model_tier].copy()
    
    @classmethod
    def estimate_savings(cls, 
                         original_model: str, 
                         optimized_model: str,
                         request_count: int = 1) -> dict:
        """
        Estimate cost savings from model optimization.
        
        Returns a dict with savings percentage and details.
        """
        original_cost = None
        optimized_cost = None
        
        for tier, config in cls.MODELS.items():
            if config["name"] == original_model:
                original_cost = config["cost"]
            if config["name"] == optimized_model:
                optimized_cost = config["cost"]
        
        if original_cost and optimized_cost:
            savings_pct = ((original_cost - optimized_cost) / original_cost) * 100
            return {
                "original_model": original_model,
                "optimized_model": optimized_model,
                "original_cost_units": original_cost * request_count,
                "optimized_cost_units": optimized_cost * request_count,
                "savings_percent": round(savings_pct, 1),
                "requests": request_count
            }
        
        return {"error": "Could not calculate savings"}


# Convenience function for quick access
def select_model(task_type: TaskType, 
                 needs_vision: bool = False,
                 needs_structured_output: bool = False) -> str:
    """Quick access to model selection."""
    return ModelSelector.get_model(task_type, needs_vision, needs_structured_output)
