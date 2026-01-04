"""Gemini Computer Use Agent Loop (Async version) with Session Memory.

COST OPTIMIZATION: Implements context window sliding to prevent token explosion.
"""
import asyncio
import re
import uuid
import time
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any

from google import genai
from google.genai import types
from google.genai.types import Content, Part

from config import GOOGLE_API_KEY, MAX_AGENT_TURNS, SCREEN_WIDTH, SCREEN_HEIGHT
from browser import BrowserController
from models import ActionStep, WorkflowRecord, TaskStatus, SessionContext
from storage import save_screenshot
from observability import (
    log as logger,
    bind_context,
    SessionMetrics,
    AGENT_TASKS,
    AGENT_TURN_DURATION,
    AGENT_TURNS_PER_TASK,
    GEMINI_API_CALLS,
    GEMINI_API_DURATION,
    BROWSER_ACTIONS,
    BROWSER_ACTION_DURATION,
)
from token_calculator import get_token_calculator


class ComputerUseAgent:
    """
    Agent that uses Gemini 2.5 Computer Use to control a browser.
    
    COST OPTIMIZATION:
    - Uses context window sliding to prevent token explosion
    - Compresses prompts while preserving critical information
    
    NOW WITH SESSION MEMORY: Maintains context across multiple tasks
    within the same user session (until "End Session" is pressed).
    """

    MODEL_NAME = "gemini-2.5-computer-use-preview-10-2025"
    MAX_CONTEXT_TURNS = 10  # COST OPTIMIZATION: Keep only last N turns to prevent token explosion

    def __init__(
        self,
        on_step: Optional[Callable[[ActionStep, str], None]] = None,
        on_status_change: Optional[Callable[[TaskStatus, str], None]] = None,
        browser: Optional[BrowserController] = None,
        session_context: Optional[SessionContext] = None,
        session_metrics: Optional[SessionMetrics] = None,
    ):
        """
        Initialize the agent.
        
        Args:
            on_step: Callback called after each action with (step_data, screenshot_base64)
            on_status_change: Callback called when task status changes
            browser: Optional existing BrowserController to use (for persistent sessions)
            session_context: CRITICAL - Persistent memory across tasks in this session
        """
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.browser = browser if browser else BrowserController()
        self._owns_browser = browser is None
        self.on_step = on_step
        self.on_status_change = on_status_change
        
        # Session memory - this persists across agent.run() calls
        self.session_context = session_context or SessionContext(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat()
        )
        
        # Session metrics for real-time tracking
        self.session_metrics = session_metrics

        self.task_id: Optional[str] = None
        self.steps: List[ActionStep] = []
        self.status: TaskStatus = TaskStatus.PENDING
        self._stop_requested = False

    def _notify_status(self, status: TaskStatus, message: str = ""):
        """Update status and notify via callback."""
        self.status = status
        if self.on_status_change:
            self.on_status_change(status, message)

    def _notify_step(self, step: ActionStep, screenshot_b64: str):
        """Notify about a completed step."""
        if self.on_step:
            self.on_step(step, screenshot_b64)

    def stop(self):
        """Request the agent to stop after the current step."""
        self._stop_requested = True

    async def run(
        self, 
        goal: str, 
        start_url: str = "about:blank", 
        previous_workflow: Optional[Dict] = None
    ) -> WorkflowRecord:
        """
        Run the agent loop to achieve a goal (async version).
        
        Args:
            goal: The task description
            start_url: Initial URL
            previous_workflow: Optional dictionary containing a previously successful workflow for this goal.
                               Should contain 'steps' with actions, args, etc.
        
        Returns a WorkflowRecord with all steps taken.
        """
        self.task_id = str(uuid.uuid4())
        self.steps = []
        self._stop_requested = False
        # self._notify_status(TaskStatus.RUNNING, f"Starting task: {goal}")

        # Start browser if not already running
        if not self.browser.is_started:
            await self.browser.start(start_url)
        else:
            # Browser already open, navigate to start_url if provided and different
            if start_url and start_url != "about:blank":
                try:
                    await self.browser.page.goto(start_url)
                except:
                    pass  # Ignore navigation errors

        try:
            # ==============================================
            # BUILD CONTEXT PROMPT WITH SESSION MEMORY
            # ==============================================
            logger.info(
                "agent_run_started",
                task_id=self.task_id,
                goal=goal[:100],
                clipboard=self.session_context.clipboard,
                previous_tasks=len(self.session_context.task_history),
            )
            AGENT_TASKS.labels(status="started").inc()
            
            # Add current instruction to session memory
            self.session_context.user_instructions.append(goal)
            
            # Build the master context prompt
            context_parts = []
            
            # 1. SESSION MEMORY CONTEXT (HIGHEST PRIORITY)
            context_parts.append("=" * 60)
            context_parts.append("SESSION MEMORY - YOU MUST USE THIS INFORMATION")
            context_parts.append("=" * 60)
            
            if self.session_context.clipboard:
                context_parts.append(f"\nCLIPBOARD (last copied value): {self.session_context.clipboard}")
                context_parts.append("   ↳ When user says 'paste', use this value!")
            
            if self.session_context.last_copied_values:
                context_parts.append(f"\nALL COPIED VALUES (in order): {self.session_context.last_copied_values}")
            
            if self.session_context.important_notes:
                context_parts.append(f"\nIMPORTANT NOTES:")
                for key, value in self.session_context.important_notes.items():
                    context_parts.append(f"   - {key}: {value}")
            
            if self.session_context.task_history:
                context_parts.append(f"\nPREVIOUS TASKS IN THIS SESSION:")
                for i, task in enumerate(self.session_context.task_history[-5:], 1):  # Last 5 tasks
                    context_parts.append(f"   {i}. {task.get('goal', 'N/A')} → Result: {task.get('result', 'completed')}")
            
            if self.session_context.current_url:
                context_parts.append(f"\nCURRENT BROWSER URL: {self.session_context.current_url}")
            
            # 1.5. STATIC REFERENCE DATA - LAZY LOADING
            # Only load if workflow steps mention static_data OR goal matches with high score
            static_data_loaded = False
            static_data_context = []
            
            # Check if reference workflow mentions static data lookup
            needs_static_lookup = False
            if previous_workflow:
                workflow_str = str(previous_workflow).lower()
                if "static" in workflow_str or "static_data" in workflow_str:
                    needs_static_lookup = True
                # Also check if workflow mentions company lookup
                if "company" in workflow_str and "id" in workflow_str:
                    needs_static_lookup = True
            
            # Also check goal for high-confidence keywords
            goal_lower = goal.lower()
            static_keywords = ["company id", "download hammer", "western", "adobe", "vonage", "company_id", "get the id"]
            if any(kw in goal_lower for kw in static_keywords):
                needs_static_lookup = True
            
            if needs_static_lookup:
                try:
                    from pinecone_service import PineconeService
                    from screenshot_embedder import get_embedder
                    
                    ps = PineconeService()
                    embedder = get_embedder()
                    goal_embedding = embedder.embed_query(goal)
                    static_records = ps.query_static_data(goal_embedding, top_k=5)
                    
                    # Higher threshold for lazy loading (0.25 instead of 0.15)
                    relevant_records = [r for r in static_records if r.get("score", 0) >= 0.25]
                    
                    if relevant_records:
                        static_data_loaded = True
                        context_parts.append("\n" + "=" * 60)
                        context_parts.append("STATIC REFERENCE DATA - Company lookup information")
                        context_parts.append("=" * 60)
                        for i, record in enumerate(relevant_records, 1):
                            data = record.get("data", "")[:500]
                            context_parts.append(f"\n{i}. {data}")
                            static_data_context.append(data)
                        context_parts.append("")
                        print(f"[STATIC] Loaded {len(relevant_records)} records (lazy load triggered)")
                    else:
                        print(f"[STATIC] No relevant records found (threshold not met)")
                except Exception as static_err:
                    print(f"[STATIC] Could not fetch static data: {static_err}")
            else:
                print(f"[STATIC] Lazy load NOT triggered (no keywords/workflow match)")
            
            # 2. USER INSTRUCTION HISTORY (for conversational context)
            if len(self.session_context.user_instructions) > 1:
                context_parts.append("\n" + "=" * 60)
                context_parts.append("CONVERSATION HISTORY - Follow this flow!")
                context_parts.append("=" * 60)
                for i, instruction in enumerate(self.session_context.user_instructions, 1):
                    context_parts.append(f"   {i}. {instruction}")
            
            # 3. CURRENT USER INSTRUCTION (THIS IS WHAT YOU MUST DO NOW)
            context_parts.append("\n" + "=" * 60)
            context_parts.append("CURRENT TASK - DO THIS NOW")
            context_parts.append("=" * 60)
            context_parts.append(f"\n{goal}")
            
            # 4. CRITICAL RULES - INTELLIGENT NAVIGATION
            context_parts.append("\n" + "=" * 60)
            context_parts.append("CRITICAL RULES - ABSOLUTE PRIORITY")
            context_parts.append("=" * 60)
            context_parts.append("""
0. USER PROMPT IS KING: Your ONLY job is to execute EXACTLY what the user asked in "CURRENT TASK" above.
   - Do NOT add extra steps beyond what user explicitly requested
   - Do NOT follow saved workflows that don't match the user's current request
   - If user says "scroll down and do nothing else", you scroll ONCE and STOP. No clicks. No navigation. No extra actions.
   - SAVED WORKFLOWS below (if any) are HINTS, not commands. IGNORE them if they don't match the current task.
   - When in doubt, DO LESS. It's better to under-act than over-act.

1. STOP ON VISUAL SUCCESS: Trust your EYES (screenshot), not just the URL. If the visual elements of the goal are present (e.g., a dashboard layout, a success message), the task is DONE. Do not click buttons just to force the URL to match a specific string exactly.
2. POST-ACTION SETTLEMENT: After any major state change (Clicking 'Login', 'Submit', 'Save', or pressing Enter), you MUST pause evaluation for the next step. Redirects take time.
   - If you just logged in, expect the URL to change (e.g., to include session tokens). This is normal.
   - Do not "correct" a URL immediately after login unless you are stuck on an error page.
3. MINIMAL INTERVENTION: If you are 90% sure you are on the right page, STOP. It is better to stop early than to click a random "Home" button that might reset the session context.
4. CONTEXT AWARENESS: If a saved workflow says "Go to X", but you are ALREADY at X (visually), skip the navigation step.
5. NO HALLUCINATIONS: Do not invent steps not requested (like uploading photos, clicking extra menus, or "exploring" the UI).
6. CLIPBOARD USAGE: If user says "paste" or "paste the ID" -> USE THE CLIPBOARD VALUE from session memory above.
7. NEVER search on Google or any search engine unless explicitly asked.
""")
            
            # 5. OPTIONAL: Previously saved workflow as REFERENCE (not commands)
            if previous_workflow:
                context_parts.append("\n" + "=" * 60)
                context_parts.append("REFERENCE WORKFLOW - USE ONLY IF DIRECTLY RELEVANT TO CURRENT TASK")
                context_parts.append("=" * 60)
                context_parts.append("")
                context_parts.append("WARNING: This workflow is provided as OPTIONAL context.")
                context_parts.append("If it does NOT match the user's CURRENT TASK, IGNORE IT COMPLETELY.")
                context_parts.append("The user's prompt takes ABSOLUTE PRIORITY over this workflow.")
                context_parts.append("")
                # ==============================================
                # CHECK FORMAT: JSON_V2 (clean JSON) vs TEXT (human-readable) vs OLD (steps array)
                # ==============================================
                import json as json_module
                
                is_json_v2 = previous_workflow.get("format") == "json_v2"
                is_text_format = (
                    previous_workflow.get("format") == "new" or 
                    previous_workflow.get("system_logs")  # Old text format had system_logs
                )
                
                if is_json_v2:
                    # JSON_V2 FORMAT - Parse JSON and build minimal prompt
                    print(f"[WORKFLOW] Using JSON_V2 FORMAT (clean JSON)")
                    
                    # Parse URLs from JSON
                    try:
                        urls_raw = previous_workflow.get("urls_visited", "[]")
                        urls = json_module.loads(urls_raw) if isinstance(urls_raw, str) else urls_raw
                        if urls:
                            context_parts.append("CRITICAL URLs (NAVIGATE IN ORDER):")
                            for i, url in enumerate(urls, 1):
                                context_parts.append(f"  {i}. {url}")
                            context_parts.append("")
                    except Exception as e:
                        print(f"[WARNING] Failed to parse urls_visited: {e}")
                    
                    # Parse actions from JSON
                    try:
                        actions_raw = previous_workflow.get("actions", "{}")
                        actions = json_module.loads(actions_raw) if isinstance(actions_raw, str) else actions_raw
                        if actions:
                            context_parts.append("ACTIONS:")
                            for action, count in actions.items():
                                context_parts.append(f"  - {action}: {count}x")
                            context_parts.append("")
                    except Exception as e:
                        print(f"[WARNING] Failed to parse actions: {e}")
                    
                    # Parse steps from JSON
                    try:
                        steps_raw = previous_workflow.get("steps", "[]")
                        steps = json_module.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
                        if steps:
                            context_parts.append("EXECUTION STEPS:")
                            for step in steps[:10]:  # Limit to 10 steps for prompt size
                                step_num = step.get("step", "?")
                                url = step.get("url", "")
                                reasoning = step.get("reasoning", "")
                                step_line = f"  {step_num}. {url}"
                                if reasoning:
                                    step_line += f" → {reasoning[:100]}"
                                context_parts.append(step_line)
                            context_parts.append("")
                    except Exception as e:
                        print(f"[WARNING] Failed to parse steps: {e}")
                    
                    # Parse user prompts from JSON
                    try:
                        prompts_raw = previous_workflow.get("user_prompts", "[]")
                        prompts = json_module.loads(prompts_raw) if isinstance(prompts_raw, str) else prompts_raw
                        if prompts:
                            context_parts.append(f"ORIGINAL REQUEST: {prompts[0] if prompts else 'N/A'}")
                            context_parts.append("")
                    except Exception as e:
                        print(f"[WARNING] Failed to parse user_prompts: {e}")
                    
                    context_parts.append("=" * 60)
                    context_parts.append("[IMPORTANT] Follow these URLs and steps!")
                    context_parts.append("=" * 60)
                    
                elif is_text_format:
                    # LEGACY TEXT FORMAT - use human-readable metadata from Pinecone
                    print(f"[WORKFLOW] Using LEGACY TEXT FORMAT (pre-json_v2)")
                    
                    # Add URLs visited - CRITICAL for navigation
                    if previous_workflow.get("urls_visited"):
                        context_parts.append("CRITICAL URLs (NAVIGATE TO THESE EXACT URLs):")
                        context_parts.append(previous_workflow.get("urls_visited"))
                        context_parts.append("")
                    
                    # Add actions performed - shows what actions to take
                    if previous_workflow.get("actions_performed"):
                        context_parts.append("ACTIONS TO PERFORM:")
                        context_parts.append(previous_workflow.get("actions_performed"))
                        context_parts.append("")
                    
                    # Add system logs - contains step-by-step execution details
                    if previous_workflow.get("system_logs"):
                        system_logs = previous_workflow.get("system_logs")
                        # Truncate if too long
                        if len(system_logs) > 4000:
                            system_logs = system_logs[:4000] + "\n... [truncated]"
                        context_parts.append("EXECUTION LOG (follow these steps in order):")
                        context_parts.append(system_logs)
                        context_parts.append("")
                    
                    # Add user prompts - shows what the user originally asked
                    if previous_workflow.get("user_prompts"):
                        context_parts.append("ORIGINAL USER REQUEST (this is what worked before):")
                        context_parts.append(previous_workflow.get("user_prompts"))
                        context_parts.append("")
                    
                    context_parts.append("=" * 60)
                    context_parts.append("[IMPORTANT] Follow the URLs and steps above to complete the task!")
                    context_parts.append("=" * 60)
                else:
                    # OLD FORMAT - process steps array and execution_summary
                    print(f"[WORKFLOW] Using OLD FORMAT workflow (steps array)")
                    
                    # ALWAYS extract critical data from steps first (URLs, credentials)
                    # This prevents the model from inventing URLs when execution_summary is vague
                    critical_urls = []
                    critical_credentials = []
                    steps_data = []
                
                    try:
                        steps_data = previous_workflow.get("steps", []) if isinstance(previous_workflow, dict) else getattr(previous_workflow, 'steps', [])
                        
                        for step in steps_data:
                            if isinstance(step, dict):
                                s_action = step.get("action_type", "")
                                s_args = step.get("args", {})
                                s_url = step.get("url")
                            else:
                                s_action = getattr(step, 'action_type', "")
                                s_args = getattr(step, 'args', {})
                                s_url = getattr(step, 'url', None)
                            
                            # Extract navigation URLs
                            if s_action == "navigate" and s_args.get("url"):
                                critical_urls.append(s_args["url"])
                            elif s_url and "http" in str(s_url):
                                if s_url not in critical_urls and "about:blank" not in s_url:
                                    critical_urls.append(s_url)
                            
                            # Extract credentials (text for type actions)
                            if "type" in s_action and s_args.get("text"):
                                text = s_args["text"]
                                # Capture emails and passwords
                                if "@" in text or len(text) > 6:
                                    critical_credentials.append({
                                        "action": s_action,
                                        "text": text,
                                        "element_description": s_args.get("element_description", "input field")
                                    })
                    except Exception as e:
                        print(f"[WARNING] Error extracting critical data: {e}")
                    
                    # MANDATORY: Add critical URLs at the TOP so model NEVER invents them
                    if critical_urls:
                        context_parts.append("")
                        context_parts.append("CRITICAL URLs (USE THESE EXACT URLs - DO NOT INVENT):")
                        for i, url in enumerate(critical_urls, 1):
                            context_parts.append(f"   {i}. {url}")
                        context_parts.append("")
                    
                    # MANDATORY: Add credentials
                    if critical_credentials:
                        context_parts.append("CREDENTIALS (USE EXACTLY AS SHOWN):")
                        for cred in critical_credentials:
                            context_parts.append(f"   - {cred['element_description']}: '{cred['text']}'")
                        context_parts.append("")
                    
                    # Check if we have an AI-generated execution summary
                    execution_summary = previous_workflow.get("execution_summary") if isinstance(previous_workflow, dict) else None
                    
                    if execution_summary:
                        # Use the optimized AI summary
                        print(f"Using AI-generated execution summary + extracted critical data")
                        context_parts.append("Execution Instructions:")
                        context_parts.append("")
                        context_parts.append(execution_summary)
                    else:
                        # Fallback to raw steps (backwards compatibility)
                        print(f"No execution_summary found, using raw steps")
                        context_parts.append("GUIDE FOR EXECUTION (Dynamic Visual Relocation):")
                        context_parts.append("   - Historic coordinates (x, y) have been STRIPPED. You must find these elements again visually.")
                        context_parts.append("   - Use the 'element_description' or text to locate targets.")
                        context_parts.append("   - Credentials and text values in the steps below ARE EXACT - use them as shown.")
                        context_parts.append("")
                        
                        try:
                            print(f"DEBUG: Processing {len(steps_data)} steps from workflow")
                            
                            for i, step in enumerate(steps_data, 1):
                                if isinstance(step, dict):
                                    s_action = step.get("action_type")
                                    s_args = step.get("args", {})
                                    s_url = step.get("url")
                                else:
                                    s_action = step.action_type
                                    s_args = step.args
                                    s_url = step.url
                                
                                # --- AMNESIA SELECTIVA DE COORDENADAS ---
                                # Creamos una copia de los argumentos y eliminamos coordenadas fijas
                                # Esto fuerza al modelo a usar 'element_description' y re-calcular x/y visualmente
                                clean_args = {k: v for k, v in s_args.items() if k not in ['x', 'y', 'y_offset', 'x_offset']}
                                
                                # Build detailed step info
                                step_info = f"Step {i}: {s_action}"
                                
                                # Add URL if present
                                if s_url:
                                    step_info += f"\n     URL: {s_url}"
                                
                                # Add CLEAN args (only semantic data, no hard coordinates)
                                if clean_args:
                                    step_info += f"\n     Args: {clean_args}"
                                    
                                    # Highlight important values for visual grounding
                                    if 'element_description' in clean_args:
                                        step_info += f"\n     [LOOK FOR VISUALLY]: '{clean_args['element_description']}'"
                                    elif 'text' in clean_args and s_action == 'click_element':
                                        step_info += f"\n     [LOOK FOR TEXT]: '{clean_args['text']}'"
                                    
                                    if 'text' in clean_args and 'type' in s_action:
                                        step_info += f"\n     [TYPE]: '{clean_args['text']}'"
                                    
                                    # Highlight credentials for input fields
                                    if 'text' in clean_args and s_action not in ['click_element']:
                                        step_info += f"\n     TEXT TO TYPE: '{clean_args['text']}'"
                                    if 'url' in clean_args:
                                        step_info += f"\n     NAVIGATE TO: {clean_args['url']}"
                                
                                context_parts.append(step_info)
                                context_parts.append("")  # Empty line between steps
                        except Exception as e:
                            print(f"[WARNING] Error processing previous workflow: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    context_parts.append("=" * 60)
                    context_parts.append("[IMPORTANT] EXECUTE THE ABOVE STEPS. Use the EXACT text/credentials shown!")
                    context_parts.append("=" * 60)
            
            context_prompt = "\n".join(context_parts)
            print(f"\n[PROMPT] FULL PROMPT TO AGENT (first 2000 chars):\n{context_prompt[:2000]}")
            if len(context_prompt) > 2000:
                print(f"... [truncated, total length: {len(context_prompt)} chars]")

            # Build initial content with screenshot
            initial_screenshot = await self.browser.get_screenshot_bytes()
            contents: List[Content] = [
                Content(
                    role="user",
                    parts=[
                        Part(text=context_prompt),
                        Part.from_bytes(data=initial_screenshot, mime_type="image/png"),
                    ],
                )
            ]

            # Configure the model
            config = types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        computer_use=types.ComputerUse(
                            environment=types.Environment.ENVIRONMENT_BROWSER
                        )
                    )
                ],
                thinking_config=types.ThinkingConfig(include_thoughts=True),
            )

            step_number = 0

            for turn in range(MAX_AGENT_TURNS):
                if self._stop_requested:
                    self._notify_status(TaskStatus.STOPPED, "Stopped by user")
                    break

                # Call the model with retry logic for transient failures
                response = None
                max_retries = 3
                
                for attempt in range(max_retries):
                    try:
                        api_start = time.time()
                        response = self.client.models.generate_content(
                            model=self.MODEL_NAME,
                            contents=contents,
                            config=config,
                        )
                        api_duration = time.time() - api_start
                        
                        # Track Gemini API call in session metrics
                        if self.session_metrics:
                            self.session_metrics.record_gemini_call(api_duration)
                            
                            # --- TOKEN & COST TRACKING ---
                            try:
                                input_tokens = 0
                                output_tokens = 0
                                
                                # Try to get exact usage from metadata
                                if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
                                    input_tokens = response.usage_metadata.prompt_token_count or 0
                                    output_tokens = response.usage_metadata.candidates_token_count or 0
                                else:
                                    # Fallback to estimation
                                    print("⚠️ No usage_metadata found, estimating tokens...")
                                    calc = get_token_calculator()
                                    # Estimate prompt (context + screenshot approx)
                                    # Screenshot tokens are hard to estimate exactly without metadata (~1k-2k usually)
                                    # This is a rough fallback
                                    input_tokens = calc.estimate_tokens(str(contents)) + 1500 
                                    output_tokens = calc.estimate_tokens(response.text if response and hasattr(response, 'text') else "")
                                
                                # Calculate cost
                                calc = get_token_calculator()
                                cost = calc.calculate_cost(self.MODEL_NAME, input_tokens, output_tokens)
                                
                                # Record to metrics
                                self.session_metrics.record_tokens(self.MODEL_NAME, input_tokens, output_tokens, cost)
                                print(f"   💰 Cost: ${cost:.4f} (In: {input_tokens}, Out: {output_tokens})")
                                
                            except Exception as token_err:
                                print(f"⚠️ Error tracking tokens: {token_err}")
                        
                        # Check for valid response
                        if response and response.candidates:
                            break  # Success, exit retry loop
                        
                        # Empty response - log and retry
                        error_info = ""
                        if response and hasattr(response, 'prompt_feedback'):
                            error_info = f" Feedback: {response.prompt_feedback}"
                        print(f"⚠️ Empty API response (attempt {attempt + 1}/{max_retries}).{error_info}")
                        
                        if attempt < max_retries - 1:
                            import asyncio
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                            
                    except Exception as api_error:
                        print(f"⚠️ API call error (attempt {attempt + 1}/{max_retries}): {api_error}")
                        if attempt < max_retries - 1:
                            import asyncio
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise  # Re-raise on final attempt
                
                # Check if we got a valid response after retries
                if not response or not response.candidates:
                    error_msg = "Failed to get valid response from Gemini API after retries"
                    if response and hasattr(response, 'prompt_feedback'):
                        error_msg = f"API blocked: {response.prompt_feedback}"
                    print(f"❌ {error_msg}")
                    self._notify_status(TaskStatus.FAILED, error_msg)
                    break

                candidate = response.candidates[0]
                
                # Handle case where candidate.content is None (empty/blocked response)
                if not candidate.content or not candidate.content.parts:
                    print("⚠️ Empty candidate content, treating as end of task")
                    self._notify_status(TaskStatus.COMPLETED, "Task completed (no further actions)")
                    break
                
                contents.append(candidate.content)

                # Extract function calls
                function_calls = [
                    part.function_call
                    for part in candidate.content.parts
                    if part.function_call
                ]

                # If no function calls, the agent is done
                if not function_calls:
                    text_parts = [
                        part.text for part in candidate.content.parts if part.text
                    ]
                    final_message = " ".join(text_parts) if text_parts else "Task completed"
                    self._notify_status(TaskStatus.COMPLETED, final_message)
                    break

                # Execute each function call
                function_responses = []
                for fc in function_calls:
                    step_number += 1
                    action_name = fc.name
                    args = dict(fc.args) if fc.args else {}

                    # Extract reasoning from text parts
                    reasoning = None
                    for part in candidate.content.parts:
                        if part.text:
                            reasoning = part.text
                            break
                    
                    # --- OBSERVABILITY: Send reasoning/thinking to console only (not Mission Control) ---
                    # The full reasoning is captured in step.reasoning and shown in SYSTEM LOGS
                    if reasoning:
                        print(f"[THINKING]: {reasoning[:150]}..." if len(reasoning) > 150 else f"[THINKING]: {reasoning}")

                    # Check for safety decision - auto-acknowledge for now
                    # In a full implementation, you would prompt the user
                    safety_ack = None
                    if 'safety_decision' in args:
                        safety_decision = args.pop('safety_decision')  # Remove from args before executing
                        decision_type = ""
                        explanation = ""
                        if isinstance(safety_decision, dict):
                            decision_type = safety_decision.get('decision', '')
                            explanation = safety_decision.get('explanation', '')
                        # Auto-acknowledge all safety decisions
                        safety_ack = "true"
                        print(f"Safety decision ({decision_type}): {explanation}")
                        # Only notify for actual safety decisions - this is meaningful
                        if decision_type:
                            self._notify_status(TaskStatus.RUNNING, f"Safety check: {decision_type}")

                    # --- STRATEGIC MILESTONE DETECTION ---
                    # Only send meaningful high-level messages to Mission Control
                    # Low-level "Executing: click_at" messages are NOT sent (they're in SYSTEM LOGS)
                    
                    milestone_message = None
                    
                    # Detect navigation milestones
                    if action_name == "navigate" and 'url' in args:
                        url = args['url']
                        if 'signin' in url or 'login' in url:
                            milestone_message = f"Navigating to login..."
                        elif 'dash' in url:
                            milestone_message = f"Loading dashboard..."
                        else:
                            domain = url.split('/')[2] if len(url.split('/')) > 2 else url
                            milestone_message = f"Opening {domain}..."
                    
                    # Detect credential input (but don't expose password)
                    elif 'type' in action_name and 'text' in args:
                        text = args['text']
                        if '@' in text:
                            milestone_message = f"Entering credentials..."
                        elif len(text) > 20 or '.' in text:  # Likely password or long input
                            milestone_message = None  # Don't announce password entry
                        else:
                            milestone_message = None  # Skip small text inputs
                    
                    # Detect form submission (click on login/submit buttons)
                    elif action_name == "click_at" and reasoning:
                        reason_lower = reasoning.lower()
                        if any(kw in reason_lower for kw in ['sign in', 'login', 'submit', 'save']):
                            milestone_message = f"Submitting form..."
                        elif any(kw in reason_lower for kw in ['switch', 'change', 'select', 'profile']):
                            milestone_message = f"Changing context..."
                    
                    # Only notify if this is a meaningful milestone
                    if milestone_message:
                        self._notify_status(TaskStatus.RUNNING, milestone_message)
                    
                    # Console logging for debugging (always log all actions)
                    log_message = f"Executing: {action_name}"
                    if 'element_description' in args:
                        log_message += f" on '{args['element_description']}'"
                    elif 'text' in args:
                        log_message += f" typing '{args['text'][:30]}...'" if len(str(args.get('text', ''))) > 30 else f" typing '{args['text']}'"
                    elif 'url' in args:
                        log_message += f" → {args['url']}"
                    print(f"\n{log_message} | Full args: {args}")
                    
                    # Execute the action (async)
                    action_start = time.time()
                    result = await self.browser.execute_action(action_name, args)
                    action_duration = time.time() - action_start
                    
                    # Track browser action in session metrics
                    if self.session_metrics:
                        self.session_metrics.record_browser_action(action_duration)
                    
                    print(f"   [OK] Result: url={result.get('url', 'N/A')}")
                    
                    # ==============================================
                    # UPDATE SESSION CONTEXT AFTER EACH ACTION
                    # ==============================================
                    
                    # Track current URL
                    self.session_context.current_url = result.get("url")
                    
                    # Detect COPY operations (Ctrl+C) - try to capture clipboard 
                    if action_name == "key_combination":
                        keys = args.get("keys", "").lower()
                        if "control+c" in keys or "ctrl+c" in keys:
                            print("[CLIPBOARD] COPY DETECTED! Attempting to read clipboard...")
                            # The actual clipboard content is tricky to get from browser
                            # But we can note that a copy happened
                            # The user should mention what was copied for us to track
                            # For now, we'll parse it from the agent's reasoning
                            if reasoning:
                                # Try to extract what was copied from reasoning
                                # Look for patterns like "copied US66254" or "the ID is US66254"
                                id_match = re.search(r'(?:copied|copy|ID is|ID:)\s*["\']?([A-Z]{2}[\d]+|[A-Z0-9\-]+)', reasoning, re.IGNORECASE)
                                if id_match:
                                    copied_value = id_match.group(1)
                                    self.session_context.clipboard = copied_value
                                    self.session_context.last_copied_values.append(copied_value)
                                    print(f"   [CLIPBOARD] STORED IN CLIPBOARD: {copied_value}")
                            
                    # If reasoning mentions copying something specific, store it
                    if reasoning:
                        # Look for "US" + numbers pattern (company IDs)
                        company_id_match = re.search(r'\b(US\d{5,}|CCR-\d+)\b', reasoning)
                        if company_id_match and "cop" in reasoning.lower():
                            copied_id = company_id_match.group(1)
                            if copied_id not in self.session_context.last_copied_values:
                                self.session_context.clipboard = copied_id
                                self.session_context.last_copied_values.append(copied_id)
                                print(f"   [CLIPBOARD] EXTRACTED & STORED: {copied_id}")
                    
                    # ==============================================
                    # DETECT HAMMER DOWNLOAD (.xlsm click)
                    # Triggers automatic: Clear → DuckDB ETL → Index
                    # ==============================================
                    if action_name == "click_at":
                        current_url = result.get("url", "")
                        
                        # Check if we're on the admin/questions page (where hammers are downloaded)
                        is_hammer_page = "admin/questions" in current_url or "admin" in current_url.lower()
                        
                        # Check if reasoning mentions .xlsm or hammer
                        mentions_hammer = False
                        if reasoning:
                            reasoning_lower = reasoning.lower()
                            mentions_hammer = ".xlsm" in reasoning_lower or "hammer" in reasoning_lower or "download" in reasoning_lower
                        
                        if is_hammer_page and mentions_hammer:
                            print("\n" + "=" * 60)
                            print("[DOWNLOAD] HAMMER FILE DOWNLOAD DETECTED!")
                            print("=" * 60)
                            
                            # Store in session context
                            self.session_context.important_notes["hammer_download_pending"] = "true"
                            self.session_context.important_notes["hammer_download_url"] = current_url
                            self.session_context.important_notes["hammer_download_time"] = datetime.now().isoformat()
                            
                            # Notify via status callback
                            if self.on_status_change:
                                self.on_status_change(
                                    TaskStatus.RUNNING, 
                                    "Hammer download detected! Waiting for file to complete..."
                                )
                            
                            # Wait for download to complete and trigger indexing
                            try:
                                from download_tracker import get_download_tracker
                                from hammer_etl import is_hammer_file
                                
                                # Wait longer for download to complete (up to 30 seconds)
                                new_file = None
                                
                                for wait_attempt in range(10):  # 10 attempts x 3 seconds = 30s max
                                    await asyncio.sleep(3)
                                    
                                    # Method 1: Check browser's direct download handler
                                    browser_download = self.browser.get_latest_download()
                                    if browser_download and is_hammer_file(browser_download):
                                        new_file = browser_download
                                        print(f"[DOWNLOAD] Got from browser handler: {new_file}")
                                        break
                                    
                                    # Method 2: Check file tracker (backup)
                                    tracker = get_download_tracker()
                                    tracker_file = tracker.check_for_new_hammer()
                                    if tracker_file and is_hammer_file(tracker_file):
                                        new_file = tracker_file
                                        print(f"[DOWNLOAD] Got from file tracker: {new_file}")
                                        break
                                    
                                    print(f"[DOWNLOAD] Waiting for download... (attempt {wait_attempt + 1}/10)")
                                
                                if new_file:
                                    print(f"[AUTO-INDEX] Hammer file ready: {new_file}")
                                    
                                    # Notify UI that indexing is starting
                                    if self.on_status_change:
                                        filename = new_file.split('/')[-1] if '/' in new_file else new_file.split(chr(92))[-1]
                                        self.on_status_change(
                                            TaskStatus.RUNNING,
                                            f"Auto-indexing: {filename}..."
                                        )
                                    
                                    # Trigger the full indexing workflow
                                    from hammer_indexer import get_hammer_indexer
                                    
                                    def progress_callback(msg: str, pct: float):
                                        if self.on_status_change:
                                            self.on_status_change(TaskStatus.RUNNING, f"Indexing: {msg}")
                                    
                                    indexer = get_hammer_indexer(on_progress=progress_callback)
                                    index_result = indexer.index_hammer(new_file, clear_existing=True)
                                    
                                    if index_result.get("success"):
                                        records = index_result.get("records_count", 0)
                                        filename = new_file.split('/')[-1] if '/' in new_file else new_file.split(chr(92))[-1]
                                        self.session_context.important_notes["hammer_indexed"] = "true"
                                        self.session_context.important_notes["hammer_records"] = str(records)
                                        self.session_context.important_notes["hammer_file"] = filename
                                        
                                        if self.on_status_change:
                                            self.on_status_change(
                                                TaskStatus.RUNNING,
                                                f"Hammer indexed: {records} records ready for queries"
                                            )
                                        print(f"[AUTO-INDEX] [SUCCESS] Indexed {records} records")
                                    else:
                                        print(f"[AUTO-INDEX] [FAILED] {index_result.get('error')}")
                                        
                                else:
                                    print("[AUTO-INDEX] Download did not complete in time (30s timeout)")
                                    if self.on_status_change:
                                        self.on_status_change(
                                            TaskStatus.RUNNING,
                                            "Download timeout - you may need to manually index the hammer"
                                        )
                                    
                            except Exception as e:
                                print(f"[AUTO-INDEX] Error in auto-indexing: {e}")
                                import traceback
                                traceback.print_exc()

                    # Capture screenshot (async)
                    try:
                        screenshot_bytes = await self.browser.get_screenshot_bytes()
                        screenshot_b64 = await self.browser.get_screenshot_base64()
                        screenshot_path = save_screenshot(
                            self.task_id, step_number, screenshot_bytes
                        )
                    except Exception as e:
                        print(f"⚠️ Screenshot failed (browser likely closed): {e}")
                        screenshot_path = "error_screenshot.png"
                        screenshot_b64 = ""
                        # If critical browser error, might want to break loop, but let's try to verify connection
                        if "TargetClosed" in str(e):
                            raise e  # Re-raise to trigger task failure cleanup

                    # Create step record
                    step = ActionStep(
                        step_number=step_number,
                        action_type=action_name,
                        args=args,
                        screenshot_path=screenshot_path,
                        url=result.get("url"),
                        timestamp=datetime.now().isoformat(),
                        reasoning=reasoning,
                    )
                    self.steps.append(step)
                    self._notify_step(step, screenshot_b64)
                    print(f"   [STEP] Step {step_number} recorded")

                    # Build function response - include safety_acknowledgement if needed
                    response_data: Dict[str, Any] = {"url": result.get("url", "")}
                    if safety_ack:
                        response_data["safety_acknowledgement"] = safety_ack

                    function_responses.append(
                        types.FunctionResponse(
                            name=action_name,
                            response=response_data,
                            parts=[
                                types.FunctionResponsePart(
                                    inline_data=types.FunctionResponseBlob(
                                        mime_type="image/png",
                                        data=screenshot_bytes,
                                    )
                                )
                            ],
                        )
                    )

                # Add function responses to conversation
                contents.append(
                    Content(
                        role="user",
                        parts=[Part(function_response=fr) for fr in function_responses],
                    )
                )
                
                # COST OPTIMIZATION: Sliding window to prevent token explosion
                # Keep first message (system prompt) + last MAX_CONTEXT_TURNS * 2 messages
                max_messages = self.MAX_CONTEXT_TURNS * 2  # 2 messages per turn (request + response)
                if len(contents) > max_messages + 1:  # +1 for initial system prompt
                    original_length = len(contents)
                    contents = contents[:1] + contents[-(max_messages):]
                    print(f"[COST] Context window trimmed: {original_length} -> {len(contents)} messages")

            else:
                # Max turns reached
                self._notify_status(
                    TaskStatus.COMPLETED, f"Reached max turns ({MAX_AGENT_TURNS})"
                )

        except Exception as e:
            self._notify_status(TaskStatus.FAILED, str(e))
            raise

        finally:
            # Don't close browser - keep it persistent for next task
            # BUT update session context with final state
            try:
                self.session_context.current_url = await self.browser.get_current_url()
            except:
                pass

        # ==============================================
        # SAVE TASK TO SESSION HISTORY
        # ==============================================
        task_summary = {
            "goal": goal,
            "result": "completed",
            "steps_count": len(self.steps),
            "final_url": self.session_context.current_url,
            "timestamp": datetime.now().isoformat(),
        }
        self.session_context.task_history.append(task_summary)
        print(f"\n[COMPLETE] TASK COMPLETE. Session has {len(self.session_context.task_history)} tasks in history.")
        print(f"   Clipboard: {self.session_context.clipboard}")
        print(f"   Copied values: {self.session_context.last_copied_values}")
        
        # ==============================================
        # GUARDRAIL VALIDATION
        # ==============================================
        try:
            from guardrails import (
                GuardrailContext, 
                get_guardrail_service,
                parse_workflow_for_guardrails
            )
            
            # Build context for guardrail validation
            reference_data = parse_workflow_for_guardrails(previous_workflow) if previous_workflow else {}
            
            # Build actual action counts
            actual_actions = {}
            for step in self.steps:
                action = step.action_type
                actual_actions[action] = actual_actions.get(action, 0) + 1
            
            # Build actual URLs
            actual_urls = []
            for step in self.steps:
                if step.url and step.url not in actual_urls:
                    actual_urls.append(step.url)
            
            # Check if static data was referenced in any reasoning
            static_data_referenced = False
            if static_data_loaded and static_data_context:
                for step in self.steps:
                    if step.reasoning:
                        for static_content in static_data_context:
                            # Check if any part of static data appears in reasoning
                            if any(word in step.reasoning.lower() for word in static_content.lower().split()[:5]):
                                static_data_referenced = True
                                break
            
            ctx = GuardrailContext(
                reference_step_count=reference_data.get("reference_step_count"),
                reference_actions=reference_data.get("reference_actions", {}),
                reference_urls=reference_data.get("reference_urls", []),
                reference_final_url=reference_data.get("reference_final_url"),
                actual_step_count=len(self.steps),
                actual_actions=actual_actions,
                actual_urls=actual_urls,
                actual_final_url=self.session_context.current_url,
                actual_steps=[{"action_type": s.action_type, "url": s.url, "reasoning": s.reasoning} for s in self.steps],
                static_data_loaded=static_data_loaded,
                static_data_content=static_data_context,
                static_data_referenced_in_reasoning=static_data_referenced,
                task_completed_successfully=(self.status == TaskStatus.COMPLETED),
            )
            
            # Run all validators
            service = get_guardrail_service()
            results = service.validate_all(ctx)
            summary = service.get_summary(results)
            
            # Record to session metrics
            if self.session_metrics:
                self.session_metrics.record_guardrail_result(summary)
            
            # Log guardrail results
            if summary.get("drift_detected"):
                print(f"[GUARDRAIL] ⚠️ DRIFT DETECTED: {summary.get('validators', {})}")
            elif summary.get("adaptive_recovery"):
                print(f"[GUARDRAIL] ✓ Adaptive recovery detected (not drift)")
            else:
                print(f"[GUARDRAIL] ✓ All validators passed")
            
            if summary.get("context_pollution"):
                print(f"[GUARDRAIL] ⚠️ CONTEXT POLLUTION: static data loaded but not used")
                
        except Exception as guardrail_err:
            print(f"[GUARDRAIL] Error during validation: {guardrail_err}")

        # Build workflow record
        workflow = WorkflowRecord(
            id=self.task_id,
            name=f"Task {self.task_id[:8]}",
            description=goal,
            steps=self.steps,
            created_at=datetime.now().isoformat(),
            tags=[],
        )

        return workflow
