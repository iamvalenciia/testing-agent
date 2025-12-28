"""FastAPI backend for the Computer Use Agent."""
import asyncio
import json
import config  # Load environment variables from .env
import uuid
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    TaskRequest,
    TaskResponse,
    TaskStatus,
    SaveWorkflowRequest,
    ActionStep,
    WorkflowRecord,
    SessionContext,
)
from agent import ComputerUseAgent
from browser import BrowserController
from storage import save_workflow, load_workflow, list_workflows, delete_workflow
from pinecone_service import PineconeService, IndexType
from download_tracker import get_download_tracker
from hammer_indexer import get_hammer_indexer
from goal_decomposer import get_goal_decomposer, SubTask
import os

# Initialize services
pinecone_service = PineconeService()


# Store active tasks
active_tasks: Dict[str, Dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Computer Use Agent Backend starting...")
    yield
    print("Computer Use Agent Backend shutting down...")


app = FastAPI(
    title="Computer Use Agent API",
    description="API for controlling a browser via Gemini 2.5 Computer Use",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/workflows")
async def get_workflows():
    """List all saved workflows."""
    return list_workflows()


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a specific workflow by ID."""
    workflow = load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.delete("/workflows/{workflow_id}")
async def remove_workflow(workflow_id: str):
    """Delete a workflow."""
    if delete_workflow(workflow_id):
        return {"status": "deleted", "id": workflow_id}
    raise HTTPException(status_code=404, detail="Workflow not found")


@app.post("/workflows/save")
async def save_current_workflow(request: SaveWorkflowRequest):
    """Save a task's steps as a reusable workflow and index in Pinecone."""
    if request.task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = active_tasks[request.task_id]
    
    # Extract category from tags (first tag is the category)
    category = request.tags[0] if request.tags else "steps"
    
    workflow = WorkflowRecord(
        id=request.task_id,
        name=request.name,
        description=request.description,
        steps=task_data.get("steps", []),
        created_at=datetime.now().isoformat(),
        tags=request.tags,
        category=category,
    )
    
    # 1. Save to disk
    filepath = save_workflow(workflow)
    
    # 2. Generate AI Summary for efficient execution
    execution_summary = None
    try:
        from workflow_summarizer import get_summarizer
        summarizer = get_summarizer()
        
        # Convert steps to dict format for summarizer
        steps_as_dicts = [s.model_dump() for s in workflow.steps]
        
        execution_summary = summarizer.summarize_workflow(
            workflow_name=workflow.name,
            workflow_description=workflow.description,
            steps=steps_as_dicts
        )
        print(f"✅ Generated execution summary for '{workflow.name}'")
        print(f"📝 Summary preview:\n{execution_summary[:500]}...")
    except Exception as e:
        print(f"⚠️ Failed to generate workflow summary: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Index in Pinecone with BOTH raw steps AND execution summary
    pinecone_indexed = False
    try:
        # Generate embedding using Pinecone Inference API (llama-text-embed-v2 = 1024 dims)
        text_to_embed = f"{workflow.name}: {workflow.description}"
        embedding = pinecone_service.pc.inference.embed(
            model="llama-text-embed-v2",
            inputs=[text_to_embed],
            parameters={"input_type": "passage"}
        ).data[0].values
        
        # Upsert to steps-index with execution_summary
        pinecone_service.upsert_step(
            action_type=category,
            goal_description=workflow.name,
            step_details={
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "step_count": len(workflow.steps),
                "tags": workflow.tags,
                "steps": [s.model_dump() for s in workflow.steps],  # Keep raw steps as backup
                "execution_summary": execution_summary,  # NEW: AI-generated summary for execution
            },
            embedding=embedding,
            efficiency_score=1.0,
        )
        pinecone_indexed = True
        print(f"✅ Workflow '{workflow.name}' indexed in Pinecone steps-index")
    except Exception as e:
        print(f"⚠️ Failed to index workflow in Pinecone: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Generate screenshot embeddings and index for visual search
    screenshot_embeddings_indexed = 0
    try:
        from screenshot_embedder import get_embedder
        from pathlib import Path
        embedder = get_embedder()
        
        for step in workflow.steps:
            if step.screenshot_path and Path(step.screenshot_path).exists():
                # Generate context string for better embeddings
                context = f"Action: {step.action_type}"
                if step.url:
                    context += f" | URL: {step.url}"
                if step.reasoning:
                    context += f" | {step.reasoning[:200]}"
                
                # Generate multimodal embedding
                embedding = embedder.embed_image(step.screenshot_path, include_context=context)
                
                # Store in Pinecone
                pinecone_service.upsert_screenshot(
                    workflow_id=workflow.id,
                    step_number=step.step_number,
                    embedding=embedding,
                    metadata={
                        "workflow_name": workflow.name,
                        "action_type": step.action_type,
                        "url": step.url,
                        "screenshot_path": step.screenshot_path,
                        "reasoning": step.reasoning[:500] if step.reasoning else None,
                    }
                )
                screenshot_embeddings_indexed += 1
        
        if screenshot_embeddings_indexed > 0:
            print(f"✅ Screenshot embeddings indexed: {screenshot_embeddings_indexed}")
    except Exception as e:
        print(f"⚠️ Failed to index screenshots: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        "status": "saved",
        "id": workflow.id,
        "path": filepath,
        "category": category,
        "pinecone_indexed": pinecone_indexed,
        "has_summary": execution_summary is not None,
        "screenshots_indexed": screenshot_embeddings_indexed,
    }



@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent control.
    
    Client sends:
        {"type": "start", "goal": "...", "start_url": "..."}
        {"type": "stop"}
        {"type": "close_browser"}
    
    Server sends:
        {"type": "status", "status": "running", "message": "..."}
        {"type": "step", "step": {...}, "screenshot": "base64..."}
        {"type": "completed", "workflow_id": "..."}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    agent: Optional[ComputerUseAgent] = None
    task_id: Optional[str] = None
    agent_task: Optional[asyncio.Task] = None
    
    # Persistent browser for this WebSocket session
    persistent_browser: Optional[BrowserController] = None
    
    # ==============================================
    # PERSISTENT SESSION CONTEXT - THE MEMORY!
    # This lives for the ENTIRE WebSocket session
    # It's shared between ALL tasks until "End Session"
    # ==============================================
    session_context = SessionContext(
        session_id=str(uuid.uuid4()),
        created_at=datetime.now().isoformat()
    )
    print(f"\n🧠 NEW SESSION STARTED: {session_context.session_id}")

    async def send_json(data: dict):
        """Helper to send JSON message."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            print(f"Error sending JSON: {e}")

    try:
        while True:
            # Receive message from client
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=0.5
                )
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "start":
                    goal = message.get("goal", "")
                    start_url = message.get("start_url", "")
                    step_offset = message.get("step_offset", 0)
                    
                    if not goal:
                        await send_json({"type": "error", "message": "Goal is required"})
                        continue
                    
                    # ==============================================
                    # PROCESS SPECIAL COMMANDS IN GOAL
                    # ==============================================
                    import re
                    
                    # Check for "remember: VALUE" or "clipboard: VALUE" commands
                    remember_match = re.match(r'^(?:remember|clipboard|store):\s*(.+)$', goal, re.IGNORECASE)
                    if remember_match:
                        value_to_remember = remember_match.group(1).strip()
                        session_context.clipboard = value_to_remember
                        session_context.last_copied_values.append(value_to_remember)
                        print(f"📋 USER MANUALLY SET CLIPBOARD: {value_to_remember}")
                        await send_json({
                            "type": "status",
                            "status": "idle",
                            "message": f"Remembered: {value_to_remember}",
                        })
                        continue  # Don't run agent, just store the value
                    
                    # Check for "note: KEY=VALUE" to store important info
                    note_match = re.match(r'^note:\s*(\w+)\s*=\s*(.+)$', goal, re.IGNORECASE)
                    if note_match:
                        key = note_match.group(1).strip()
                        value = note_match.group(2).strip()
                        session_context.important_notes[key] = value
                        print(f"📌 USER STORED NOTE: {key} = {value}")
                        await send_json({
                            "type": "status",
                            "status": "idle",
                            "message": f"Noted: {key} = {value}",
                        })
                        continue

                    # Cancel any running agent task
                    if agent_task and not agent_task.done():
                        agent_task.cancel()
                        try:
                            await agent_task
                        except asyncio.CancelledError:
                            pass

                    task_id = str(uuid.uuid4())
                    active_tasks[task_id] = {"steps": [], "status": TaskStatus.PENDING}

                    # Callbacks that send messages directly via WebSocket
                    def on_step(step: ActionStep, screenshot_b64: str):
                        # Adjust step number with offset for accumulated display
                        adjusted_step = ActionStep(
                            step_number=step.step_number + step_offset,
                            action_type=step.action_type,
                            args=step.args,
                            screenshot_path=step.screenshot_path,
                            url=step.url,
                            timestamp=step.timestamp,
                            reasoning=step.reasoning,
                        )
                        active_tasks[task_id]["steps"].append(adjusted_step)
                        # Use asyncio.create_task to send without blocking
                        asyncio.create_task(send_json({
                            "type": "step",
                            "step": adjusted_step.model_dump(),
                            "screenshot": screenshot_b64,
                        }))

                    def on_status_change(status: TaskStatus, msg: str):
                        active_tasks[task_id]["status"] = status
                        asyncio.create_task(send_json({
                            "type": "status",
                            "status": status.value,
                            "message": msg,
                        }))

                    # Create persistent browser if not exists
                    if persistent_browser is None:
                        persistent_browser = BrowserController()
                        # Only navigate to start_url on first browser start
                        # NOTE: Changed from google.com to about:blank - no more unnecessary searches!
                        initial_url = start_url if start_url else "about:blank"
                        await persistent_browser.start(initial_url)
                        print(f"🌐 Browser started at: {initial_url}")
                    
                    # Create agent with PERSISTENT browser AND session context
                    # The session_context is passed in - it lives across all tasks!
                    agent = ComputerUseAgent(
                        on_step=on_step,
                        on_status_change=on_status_change,
                        browser=persistent_browser,
                        session_context=session_context,  # <-- THE KEY TO MEMORY!
                    )
                    print(f"🤖 Agent created with session context: {session_context.session_id}")

                    await send_json({
                        "type": "status",
                        "status": "starting",
                        "message": f"Task {task_id} starting...",
                        "task_id": task_id,
                    })

                    # Run agent as an async task
                    # Pass empty string if browser already open to avoid navigation
                    effective_start_url = start_url if start_url else ""
                    
                    # ==============================================
                    # SMART GOAL DECOMPOSITION
                    # ==============================================
                    recommended_workflow = None
                    subtasks_to_execute = []
                    
                    # Skip decomposition for simple navigation goals
                    simple_nav_pattern = r'^(go to|navigate to|open|visit)\s+https?://'
                    is_simple_navigation = re.match(simple_nav_pattern, goal, re.IGNORECASE)
                    
                    if is_simple_navigation:
                        print(f"🔗 Simple URL navigation detected - skipping decomposition")
                    else:
                        try:
                            # Initialize goal decomposer with Pinecone service
                            decomposer = get_goal_decomposer(pinecone_service)
                            
                            # Check if goal contains multiple tasks
                            execution_plan = decomposer.get_execution_plan(goal)
                            
                            print(f"\n🧩 GOAL DECOMPOSITION RESULT:")
                            print(f"   Original goal: {goal}")
                            print(f"   Decomposed: {execution_plan['is_decomposed']}")
                            print(f"   Sub-tasks: {execution_plan['subtask_count']}")
                            
                            if execution_plan['is_decomposed'] and execution_plan['subtask_count'] > 1:
                                # Multiple sub-tasks detected
                                print(f"📋 EXECUTING {execution_plan['subtask_count']} SUB-TASKS SEQUENTIALLY:")
                                
                                for i, subtask in enumerate(execution_plan['subtasks'], 1):
                                    print(f"   {i}. {subtask.action}: {subtask.target}")
                                    if subtask.workflow_match:
                                        print(f"      ✅ Matched workflow: {subtask.workflow_match.get('goal_description', 'N/A')}")
                                
                                subtasks_to_execute = execution_plan['subtasks']
                                
                                # Notify frontend
                                await send_json({
                                    "type": "status", 
                                    "status": "planning",
                                    "message": f"Decomposed into {len(subtasks_to_execute)} tasks: {', '.join([st.action for st in subtasks_to_execute])}"
                                })
                            else:
                                # Single task - try to match workflow directly
                                print(f"📋 Single task detected, searching workflow...")
                                
                                # Generate embedding
                                embedding = pinecone_service.pc.inference.embed(
                                    model="llama-text-embed-v2",
                                    inputs=[goal],
                                    parameters={"input_type": "query"}
                                ).data[0].values
                                
                                # Extract keywords from goal for fallback
                                keywords = decomposer._extract_keywords(goal)
                                
                                # Search matches with TIERED thresholds
                                matches = pinecone_service.find_similar_steps(embedding, top_k=3)
                                print(f"🔍 DEBUG: Raw matches found: {[(m.get('goal_description'), m.get('score')) for m in matches]}")
                                
                                # Use tiered matching with keyword fallback
                                best_match = pinecone_service.get_best_step_for_goal_tiered(
                                    embedding, 
                                    keywords=keywords
                                )
                                
                                if best_match:
                                    print(f"Found existing workflow match: {best_match.get('goal_description')} (score: {best_match.get('score', 'N/A')})")
                                    # Parse the JSON string back to dict/list
                                    raw_details = best_match.get("step_details", "{}")
                                    
                                    # Handle case where it might be already dict or string
                                    if isinstance(raw_details, str):
                                        try:
                                            recommended_workflow = json.loads(raw_details)
                                        except:
                                            try:
                                                import ast
                                                recommended_workflow = ast.literal_eval(raw_details)
                                                print("🔍 DEBUG: Successfully parsed workflow using ast.literal_eval (legacy format)")
                                            except Exception as e:
                                                print(f"⚠️ Failed to parse workflow details: {e}")
                                                pass
                                    elif isinstance(raw_details, dict):
                                        recommended_workflow = raw_details

                                    if recommended_workflow:
                                        workflow_name = recommended_workflow.get("name") or best_match.get("workflow_name") or "Previous Run"
                                        steps = recommended_workflow.get("steps", [])
                                        step_count = len(steps)
                                        print(f"✅ Context Loaded: '{workflow_name}' with {step_count} steps.")
                                        
                                        # Debug: Show what's in the steps
                                        print(f"📋 WORKFLOW STEPS DETAIL:")
                                        for i, s in enumerate(steps[:5], 1):  # Show first 5
                                            s_action = s.get("action_type") if isinstance(s, dict) else s.action_type
                                            s_args = s.get("args") if isinstance(s, dict) else s.args
                                            print(f"   Step {i}: {s_action} | args={s_args}")
                                        
                                        await send_json({
                                            "type": "status", 
                                            "status": "planning",
                                            "message": f"loading knowledge from: {workflow_name}"
                                        })
                                else:
                                    print(f"⚠️ No workflow match found for: {goal}")
                        except Exception as e:
                            print(f"Error in goal decomposition: {e}")
                            import traceback
                            traceback.print_exc()

                    async def run_agent_task():
                        try:
                            # Check if we have decomposed subtasks to execute
                            if subtasks_to_execute and len(subtasks_to_execute) > 1:
                                # ==============================================
                                # SEQUENTIAL SUBTASK EXECUTION
                                # ==============================================
                                print(f"\n🚀 EXECUTING {len(subtasks_to_execute)} SUBTASKS SEQUENTIALLY")
                                
                                total_steps = 0
                                all_workflows = []
                                
                                for i, subtask in enumerate(subtasks_to_execute, 1):
                                    print(f"\n{'='*50}")
                                    print(f"📌 SUBTASK {i}/{len(subtasks_to_execute)}: {subtask.action}")
                                    print(f"   Target: {subtask.target}")
                                    print(f"{'='*50}")
                                    
                                    # Get workflow from subtask match
                                    subtask_workflow = None
                                    if subtask.workflow_match:
                                        raw_details = subtask.workflow_match.get("step_details", "{}")
                                        if isinstance(raw_details, str):
                                            try:
                                                subtask_workflow = json.loads(raw_details)
                                            except:
                                                try:
                                                    import ast
                                                    subtask_workflow = ast.literal_eval(raw_details)
                                                except:
                                                    pass
                                        elif isinstance(raw_details, dict):
                                            subtask_workflow = raw_details
                                    
                                    # Notify frontend of current subtask
                                    await send_json({
                                        "type": "status",
                                        "status": "running",
                                        "message": f"Subtask {i}/{len(subtasks_to_execute)}: {subtask.action} {subtask.target}"
                                    })
                                    
                                    # Run agent for this subtask
                                    subtask_goal = f"{subtask.action} {subtask.target}"
                                    workflow = await agent.run(
                                        subtask_goal, 
                                        effective_start_url if i == 1 else "",  # Only use start_url for first subtask
                                        previous_workflow=subtask_workflow
                                    )
                                    
                                    total_steps += len(workflow.steps)
                                    all_workflows.append(workflow)
                                    
                                    print(f"   ✅ Subtask {i} completed with {len(workflow.steps)} steps")
                                
                                print(f"\n🎉 ALL {len(subtasks_to_execute)} SUBTASKS COMPLETED! Total steps: {total_steps}")
                                
                                await send_json({
                                    "type": "completed",
                                    "workflow_id": all_workflows[-1].id if all_workflows else task_id,
                                    "step_count": total_steps,
                                    "subtasks_completed": len(subtasks_to_execute),
                                })
                            else:
                                # ==============================================
                                # SINGLE TASK EXECUTION (original behavior)
                                # ==============================================
                                workflow = await agent.run(goal, effective_start_url, previous_workflow=recommended_workflow)
                                await send_json({
                                    "type": "completed",
                                    "workflow_id": workflow.id,
                                    "step_count": len(workflow.steps),
                                })
                        except asyncio.CancelledError:
                            await send_json({
                                "type": "status",
                                "status": "stopped",
                                "message": "Task cancelled",
                            })
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            await send_json({
                                "type": "error",
                                "message": str(e),
                            })

                    agent_task = asyncio.create_task(run_agent_task())

                elif msg_type == "stop":
                    if agent:
                        agent.stop()
                        await send_json({
                            "type": "status",
                            "status": "stopping",
                            "message": "Stop requested",
                        })

                elif msg_type == "close_browser":
                    if persistent_browser:
                        await persistent_browser.stop()
                        persistent_browser = None
                        await send_json({
                            "type": "status",
                            "status": "idle",
                            "message": "Browser closed",
                        })

                elif msg_type == "end_session":
                    # ==============================================
                    # END SESSION - CLEAR ALL MEMORY
                    # ==============================================
                    print(f"\n🔴 SESSION ENDING: {session_context.session_id}")
                    print(f"   Tasks completed: {len(session_context.task_history)}")
                    print(f"   Values copied: {session_context.last_copied_values}")
                    
                    # Stop any running task
                    if agent:
                        agent.stop()
                    if agent_task and not agent_task.done():
                        agent_task.cancel()
                        try:
                            await agent_task
                        except asyncio.CancelledError:
                            pass
                    
                    # Close browser
                    if persistent_browser:
                        await persistent_browser.stop()
                        persistent_browser = None
                    
                    # RESET session context to fresh state
                    session_context = SessionContext(
                        session_id=str(uuid.uuid4()),
                        created_at=datetime.now().isoformat()
                    )
                    
                    await send_json({
                        "type": "status",
                        "status": "idle",
                        "message": f"Session ended. Memory cleared. New session: {session_context.session_id}",
                    })
                    print(f"🧠 NEW SESSION CREATED: {session_context.session_id}")

                elif msg_type == "index_hammer":
                    # ==============================================
                    # INDEX HAMMER FILE INTO PINECONE
                    # ==============================================
                    file_path = message.get("file_path")
                    
                    if not file_path:
                        # Try to find the latest downloaded hammer
                        tracker = get_download_tracker()
                        file_path = tracker.get_latest_xlsm()
                    
                    if not file_path:
                        await send_json({
                            "type": "error",
                            "message": "No hammer file found. Please download one first."
                        })
                        continue
                    
                    print(f"\n📊 INDEXING HAMMER: {os.path.basename(file_path)}")
                    
                    await send_json({
                        "type": "status",
                        "status": "indexing",
                        "message": f"Indexing {os.path.basename(file_path)}..."
                    })
                    
                    try:
                        indexer = get_hammer_indexer()
                        result = indexer.index_hammer(file_path, clear_existing=True)
                        
                        await send_json({
                            "type": "hammer_indexed",
                            "success": result.get("success", False),
                            "records_count": result.get("records_count", 0),
                            "sheets": result.get("sheets", []),
                            "file_name": result.get("file_name", ""),
                        })
                        
                        # Add to session context
                        session_context.important_notes["hammer_file"] = os.path.basename(file_path)
                        session_context.important_notes["hammer_records"] = str(result.get("records_count", 0))
                        
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        await send_json({
                            "type": "error",
                            "message": f"Failed to index hammer: {str(e)}"
                        })
                
                elif msg_type == "get_hammer_status":
                    # ==============================================
                    # GET CURRENT HAMMER INDEX STATUS
                    # ==============================================
                    stats = pinecone_service.get_hammer_stats()
                    tracker = get_download_tracker()
                    latest = tracker.get_latest_xlsm()
                    
                    await send_json({
                        "type": "hammer_status",
                        "index_stats": stats,
                        "latest_file": os.path.basename(latest) if latest else None,
                        "has_data": stats.get("total_vector_count", 0) > 0,
                    })
                
                elif msg_type == "get_latest_hammer":
                    # ==============================================
                    # GET INFO ABOUT LATEST DOWNLOADED HAMMER
                    # ==============================================
                    tracker = get_download_tracker()
                    latest = tracker.get_latest_xlsm()
                    
                    if latest:
                        info = tracker.get_hammer_info(latest)
                        await send_json({
                            "type": "latest_hammer",
                            "found": True,
                            "info": info,
                        })
                    else:
                        await send_json({
                            "type": "latest_hammer",
                            "found": False,
                            "message": "No hammer files found in Downloads folder"
                        })

                elif msg_type == "ping":
                    await send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # No message received, just continue the loop
                # This allows us to check for agent completion
                if agent_task and agent_task.done():
                    # Check if task raised an exception
                    try:
                        agent_task.result()
                    except Exception:
                        pass  # Already handled in the task
                continue

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
        if agent:
            agent.stop()
        if agent_task and not agent_task.done():
            agent_task.cancel()
        # Clean up browser on disconnect
        if persistent_browser:
            await persistent_browser.stop()
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await send_json({"type": "error", "message": str(e)})
        except:
            pass
        # Clean up browser on error
        if persistent_browser:
            await persistent_browser.stop()



@app.get("/reports/{task_id}/download")
async def download_report(task_id: str):
    """Download a zip report for a task."""
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    
    print(f"Download report requested for task: {task_id}")
    print(f"Active tasks: {list(active_tasks.keys())}")
    
    # Check active tasks first
    task_data = active_tasks.get(task_id)
    steps = []
    
    if task_data:
        steps = task_data.get("steps", [])
        print(f"Found {len(steps)} steps in active_tasks")
    else:
        # Check if saved workflow exists
        workflow = load_workflow(task_id)
        if workflow:
            steps = workflow.steps
            print(f"Found {len(steps)} steps in saved workflow")
    
    if not task_data and not steps:
        print(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task report not found. Active tasks: {list(active_tasks.keys())}")

    # Create Zip in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Add Report Summary (Markdown)
        report_content = f"# Test Report - {task_id}\n\n"
        report_content += f"Generated: {datetime.now().isoformat()}\n\n"
        report_content += "## Steps\n\n"
        
        for step in steps:
            # Handle both object and dict (depending on if loaded from active or storage)
            s_dict = step.model_dump() if hasattr(step, "model_dump") else step
            
            timestamp = s_dict.get("timestamp", "")
            action = s_dict.get("action_type", "unknown")
            args = s_dict.get("args", {})
            reasoning = s_dict.get("reasoning", "")
            
            report_content += f"### Step {s_dict.get('step_number')}\n"
            report_content += f"**Time**: {timestamp}\n"
            report_content += f"**Action**: `{action}`\n"
            report_content += f"**Args**: `{json.dumps(args)}`\n"
            if reasoning:
                report_content += f"**Reasoning**: {reasoning}\n"
            report_content += "\n---\n\n"
            
            # 2. Add Screenshot
            # Screenshots are stored in data/screenshots/{task_id}_step_{num}.png
            # We access them via storage path
            # But the step object has `screenshot_path` that is absolute.
            # We need to make it relative for the zip or just find it.
            
            # Try to find the screenshot file
            from storage import SCREENSHOTS_DIR
            step_num = s_dict.get("step_number")
            filename = f"{task_id}_step_{step_num}.png"
            file_path = SCREENSHOTS_DIR / filename
            
            if file_path.exists():
                zip_file.write(file_path, arcname=f"images/{filename}")
        
        zip_file.writestr("report.md", report_content)

    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.zip"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
