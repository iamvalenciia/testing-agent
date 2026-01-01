"""Workflow Summarizer - Uses AI to create optimized execution summaries.

This module takes raw workflow steps and generates a concise, structured
summary that's optimized for the agent to execute.

COST OPTIMIZATION: Uses model_selector for cheapest viable model.
"""
import json
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from config import GOOGLE_API_KEY
from model_selector import select_model, TaskType


class WorkflowSummarizer:
    """
    Uses Gemini to create intelligent summaries of workflows.
    
    COST OPTIMIZATION: Uses model_selector to pick cheapest model.
    
    The summaries are:
    - Structured and consistent
    - Contain only essential information
    - Optimized for agent execution
    - Include all credentials and important values
    """
    
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
    
    def summarize_workflow(
        self,
        workflow_name: str,
        workflow_description: str,
        steps: List[Dict[str, Any]]
    ) -> str:
        """
        Generate an AI-optimized execution summary for a workflow.
        
        Args:
            workflow_name: Name of the workflow
            workflow_description: What the workflow does
            steps: List of ActionStep dictionaries with action_type, args, url, etc.
        
        Returns:
            A structured execution summary string
        """
        # Build the raw steps info
        steps_text = []
        for i, step in enumerate(steps, 1):
            step_info = f"Step {i}:\n"
            step_info += f"  Action: {step.get('action_type', 'unknown')}\n"
            step_info += f"  URL: {step.get('url', 'N/A')}\n"
            
            args = step.get('args', {})
            if args:
                step_info += f"  Args: {json.dumps(args, ensure_ascii=False)}\n"
                
                # Highlight important values
                if 'text' in args:
                    step_info += f"  TEXT VALUE: '{args['text']}'\n"
                if 'url' in args:
                    step_info += f"  NAVIGATE URL: {args['url']}\n"
            
            if step.get('reasoning'):
                step_info += f"  Reasoning: {step['reasoning'][:100]}...\n"
            
            steps_text.append(step_info)
        
        raw_workflow = "\n".join(steps_text)
        
        prompt = f"""You are an expert at creating execution instructions for an AI agent that controls a web browser.

Analyze this workflow and create a CONCISE but COMPLETE execution summary.

WORKFLOW NAME: {workflow_name}
DESCRIPTION: {workflow_description}

RAW STEPS:
{raw_workflow}

Create an EXECUTION SUMMARY following this EXACT format:

```
TASK: [One line description of what to achieve]

START URL: [The URL to navigate to first]

CREDENTIALS (CRITICAL - INCLUDE ALL, NEVER REDACT):
- Email/Username: [exact value - NEVER mask or redact this]
- Password: [exact value - NEVER mask or redact this]
- Any other text inputs: [exact values]

EXECUTION STEPS:
1. [Action] - [What to do] - [Important value if any]
2. [Action] - [What to do] - [Important value if any]
...

IMPORTANT VALUES:
- [Any IDs, codes, or specific text that must be used exactly]
```

CRITICAL RULES:
1. NEVER redact, mask, or filter ANY credentials, passwords, emails, or sensitive values
2. Include ALL credentials and text values EXACTLY as they appear - no asterisks, no [REDACTED]
3. Include the EXACT text values that need to be typed, even if they look like passwords
4. Include the EXACT URLs that need to be navigated to
5. Remove only truly unnecessary details (coordinates, timestamps, etc.)
6. If there are no credentials, omit that section
7. The summary MUST contain the actual values needed to execute the workflow

Generate the summary now:"""

        try:
            # COST OPTIMIZATION: Use cheapest model for summarization
            model_name = select_model(TaskType.SUMMARIZE)
            
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistency
                    max_output_tokens=1000,
                )
            )
            
            summary = response.text.strip()
            
            # Clean up markdown code blocks if present
            if summary.startswith("```"):
                lines = summary.split("\n")
                summary = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            print(f"Generated workflow summary ({len(summary)} chars)")
            return summary
            
        except Exception as e:
            print(f"⚠️ Error generating summary: {e}")
            # Fallback to a basic summary
            return self._generate_fallback_summary(workflow_name, steps)
    
    def _generate_fallback_summary(
        self,
        workflow_name: str,
        steps: List[Dict[str, Any]]
    ) -> str:
        """Generate a basic summary without AI if the API call fails."""
        lines = [
            f"TASK: {workflow_name}",
            "",
        ]
        
        # Find first navigate action for start URL
        for step in steps:
            if step.get('action_type') == 'navigate':
                url = step.get('args', {}).get('url', '')
                if url:
                    lines.append(f"START URL: {url}")
                    break
        
        # Extract credentials from type_text_at actions
        credentials = []
        for step in steps:
            if step.get('action_type') == 'type_text_at':
                text = step.get('args', {}).get('text', '')
                if text and '@' in text:
                    credentials.append(f"- Email: {text}")
                elif text and len(text) > 4:
                    # Might be a password or important text
                    credentials.append(f"- Text: {text}")
        
        if credentials:
            lines.append("")
            lines.append("CREDENTIALS:")
            lines.extend(credentials)
        
        # List steps
        lines.append("")
        lines.append("EXECUTION STEPS:")
        for i, step in enumerate(steps, 1):
            action = step.get('action_type', 'unknown')
            args = step.get('args', {})
            text = args.get('text', '')
            url = args.get('url', step.get('url', ''))
            
            step_line = f"{i}. {action}"
            if text:
                step_line += f" - '{text}'"
            if url and action == 'navigate':
                step_line += f" - {url}"
            
            lines.append(step_line)
        
        return "\n".join(lines)


# Singleton instance
_summarizer = None

def get_summarizer() -> WorkflowSummarizer:
    """Get the singleton WorkflowSummarizer instance."""
    global _summarizer
    if _summarizer is None:
        _summarizer = WorkflowSummarizer()
    return _summarizer
