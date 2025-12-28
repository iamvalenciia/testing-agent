"""Gemini Computer Use Agent Loop (Async version) with Session Memory."""
import re
import uuid
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any

from google import genai
from google.genai import types
from google.genai.types import Content, Part

from config import GOOGLE_API_KEY, MAX_AGENT_TURNS, SCREEN_WIDTH, SCREEN_HEIGHT
from browser import BrowserController
from models import ActionStep, WorkflowRecord, TaskStatus, SessionContext
from storage import save_screenshot


class ComputerUseAgent:
    """
    Agent that uses Gemini 2.5 Computer Use to control a browser.
    
    NOW WITH SESSION MEMORY: Maintains context across multiple tasks
    within the same user session (until "End Session" is pressed).
    """

    MODEL_NAME = "gemini-2.5-computer-use-preview-10-2025"

    def __init__(
        self,
        on_step: Optional[Callable[[ActionStep, str], None]] = None,
        on_status_change: Optional[Callable[[TaskStatus, str], None]] = None,
        browser: Optional[BrowserController] = None,
        session_context: Optional[SessionContext] = None,
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
        self._notify_status(TaskStatus.RUNNING, f"Starting task: {goal}")

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
            print(f"\n🧠 SESSION MEMORY STATE:")
            print(f"   Clipboard: {self.session_context.clipboard}")
            print(f"   Copied Values History: {self.session_context.last_copied_values}")
            print(f"   Previous Tasks: {len(self.session_context.task_history)}")
            print(f"   User Instructions So Far: {self.session_context.user_instructions}")
            
            # Add current instruction to session memory
            self.session_context.user_instructions.append(goal)
            
            # Build the master context prompt
            context_parts = []
            
            # 1. SESSION MEMORY CONTEXT (HIGHEST PRIORITY)
            context_parts.append("=" * 60)
            context_parts.append("🧠 SESSION MEMORY - YOU MUST USE THIS INFORMATION")
            context_parts.append("=" * 60)
            
            if self.session_context.clipboard:
                context_parts.append(f"\n📋 CLIPBOARD (last copied value): {self.session_context.clipboard}")
                context_parts.append("   ↳ When user says 'paste', use this value!")
            
            if self.session_context.last_copied_values:
                context_parts.append(f"\n📝 ALL COPIED VALUES (in order): {self.session_context.last_copied_values}")
            
            if self.session_context.important_notes:
                context_parts.append(f"\n📌 IMPORTANT NOTES:")
                for key, value in self.session_context.important_notes.items():
                    context_parts.append(f"   - {key}: {value}")
            
            if self.session_context.task_history:
                context_parts.append(f"\n📜 PREVIOUS TASKS IN THIS SESSION:")
                for i, task in enumerate(self.session_context.task_history[-5:], 1):  # Last 5 tasks
                    context_parts.append(f"   {i}. {task.get('goal', 'N/A')} → Result: {task.get('result', 'completed')}")
            
            if self.session_context.current_url:
                context_parts.append(f"\n🌐 CURRENT BROWSER URL: {self.session_context.current_url}")
            
            # 2. USER INSTRUCTION HISTORY (for conversational context)
            if len(self.session_context.user_instructions) > 1:
                context_parts.append("\n" + "=" * 60)
                context_parts.append("💬 CONVERSATION HISTORY - Follow this flow!")
                context_parts.append("=" * 60)
                for i, instruction in enumerate(self.session_context.user_instructions, 1):
                    context_parts.append(f"   {i}. {instruction}")
            
            # 3. CURRENT USER INSTRUCTION (THIS IS WHAT YOU MUST DO NOW)
            context_parts.append("\n" + "=" * 60)
            context_parts.append("🎯 CURRENT TASK - DO THIS NOW")
            context_parts.append("=" * 60)
            context_parts.append(f"\n{goal}")
            
            # 4. CRITICAL RULES
            context_parts.append("\n" + "=" * 60)
            context_parts.append("⚠️ CRITICAL RULES - NEVER VIOLATE THESE")
            context_parts.append("=" * 60)
            context_parts.append("""
1. NEVER search on Google or any search engine unless explicitly asked
2. If user says "paste" or "paste the ID" → USE THE CLIPBOARD VALUE ABOVE
3. FOLLOW the user's CURRENT instruction, not old workflows
4. If you already completed login, DON'T login again
5. BE EFFICIENT - minimum clicks, no unnecessary actions
6. When copying text, REMEMBER to store it mentally for future paste commands
""")
            
            # 5. MANDATORY: Previously saved workflow with FULL DETAILS
            if previous_workflow:
                context_parts.append("\n" + "=" * 60)
                context_parts.append("🔑 SAVED WORKFLOW - FOLLOW THESE STEPS EXACTLY")
                context_parts.append("=" * 60)
                
                # Check if we have an AI-generated execution summary (preferred)
                execution_summary = previous_workflow.get("execution_summary") if isinstance(previous_workflow, dict) else None
                
                if execution_summary:
                    # Use the optimized AI summary
                    print(f"🚀 Using AI-generated execution summary")
                    context_parts.append("⚡ AI-Optimized Execution Instructions:")
                    context_parts.append("")
                    context_parts.append(execution_summary)
                else:
                    # Fallback to raw steps (backwards compatibility)
                    print(f"📋 No execution_summary found, using raw steps")
                    context_parts.append("⚡ You MUST use the credentials and URLs from this workflow!")
                    context_parts.append("")
                    try:
                        steps_data = previous_workflow.get("steps", []) if isinstance(previous_workflow, dict) else previous_workflow.steps
                        print(f"📋 DEBUG: Processing {len(steps_data)} steps from workflow")
                        
                        for i, step in enumerate(steps_data, 1):
                            if isinstance(step, dict):
                                s_action = step.get("action_type")
                                s_args = step.get("args", {})
                                s_url = step.get("url")
                            else:
                                s_action = step.action_type
                                s_args = step.args
                                s_url = step.url
                            
                            # Build detailed step info
                            step_info = f"Step {i}: {s_action}"
                            
                            # Add URL if present
                            if s_url:
                                step_info += f"\n     URL: {s_url}"
                            
                            # Add ALL args (this includes credentials!)
                            if s_args:
                                step_info += f"\n     Args: {s_args}"
                                
                                # Highlight important values
                                if 'text' in s_args:
                                    step_info += f"\n     📝 TEXT TO TYPE: '{s_args['text']}'"
                                if 'url' in s_args:
                                    step_info += f"\n     🌐 NAVIGATE TO: {s_args['url']}"
                            
                            context_parts.append(step_info)
                            context_parts.append("")  # Empty line between steps
                    except Exception as e:
                        print(f"⚠️ Error processing previous workflow: {e}")
                        import traceback
                        traceback.print_exc()
                
                context_parts.append("=" * 60)
                context_parts.append("⚠️ EXECUTE THE ABOVE STEPS. Use the EXACT text/credentials shown!")
                context_parts.append("=" * 60)
            
            context_prompt = "\n".join(context_parts)
            print(f"\n📧 FULL PROMPT TO AGENT (first 2000 chars):\n{context_prompt[:2000]}")
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
                        response = self.client.models.generate_content(
                            model=self.MODEL_NAME,
                            contents=contents,
                            config=config,
                        )
                        
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

                    # Execute the action (async)
                    print(f"\n🎬 EXECUTING: {action_name} with args: {args}")
                    result = await self.browser.execute_action(action_name, args)
                    print(f"   ✅ Result: url={result.get('url', 'N/A')}")
                    
                    # ==============================================
                    # UPDATE SESSION CONTEXT AFTER EACH ACTION
                    # ==============================================
                    
                    # Track current URL
                    self.session_context.current_url = result.get("url")
                    
                    # Detect COPY operations (Ctrl+C) - try to capture clipboard 
                    if action_name == "key_combination":
                        keys = args.get("keys", "").lower()
                        if "control+c" in keys or "ctrl+c" in keys:
                            print("📋 COPY DETECTED! Attempting to read clipboard...")
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
                                    print(f"   📋 STORED IN CLIPBOARD: {copied_value}")
                            
                    # If reasoning mentions copying something specific, store it
                    if reasoning:
                        # Look for "US" + numbers pattern (company IDs)
                        company_id_match = re.search(r'\b(US\d{5,}|CCR-\d+)\b', reasoning)
                        if company_id_match and "cop" in reasoning.lower():
                            copied_id = company_id_match.group(1)
                            if copied_id not in self.session_context.last_copied_values:
                                self.session_context.clipboard = copied_id
                                self.session_context.last_copied_values.append(copied_id)
                                print(f"   📋 EXTRACTED & STORED: {copied_id}")
                    
                    # ==============================================
                    # DETECT HAMMER DOWNLOAD (.xlsm click)
                    # ==============================================
                    if action_name == "click_at":
                        current_url = result.get("url", "")
                        
                        # Check if we're on the admin/questions page (where hammers are downloaded)
                        is_hammer_page = "admin/questions" in current_url or "admin" in current_url.lower()
                        
                        # Check if reasoning mentions .xlsm or hammer
                        mentions_hammer = False
                        if reasoning:
                            reasoning_lower = reasoning.lower()
                            mentions_hammer = ".xlsm" in reasoning_lower or "hammer" in reasoning_lower
                        
                        if is_hammer_page and mentions_hammer:
                            print("📥 HAMMER DOWNLOAD DETECTED!")
                            
                            # Store in session context
                            self.session_context.important_notes["hammer_download_pending"] = "true"
                            self.session_context.important_notes["hammer_download_url"] = current_url
                            
                            # Notify via status callback - this will show in the UI
                            if self.on_status_change:
                                self.on_status_change(
                                    TaskStatus.RUNNING, 
                                    "📥 Hammer download detected! Would you like to index this hammer data?"
                                )

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
                    print(f"   📸 Step {step_number} recorded")

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
        print(f"\n✅ TASK COMPLETE. Session has {len(self.session_context.task_history)} tasks in history.")
        print(f"   Clipboard: {self.session_context.clipboard}")
        print(f"   Copied values: {self.session_context.last_copied_values}")

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
