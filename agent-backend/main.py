"""FastAPI backend for the Computer Use Agent."""
import asyncio
import json
import config  # Load environment variables from .env
import uuid
from datetime import datetime
from typing import Dict, Optional, List
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

# Google OAuth imports
from google_auth import (
    get_google_auth_service,
    get_current_user,
    get_current_user_optional,
    get_websocket_token,
)

# Observability imports
from observability import (
    log as logger,
    bind_context,
    generate_trace_id,
    WEBSOCKET_CONNECTIONS,
    WEBSOCKET_MESSAGES,
    AGENT_TASKS,
    WORKFLOW_SAVES,
    SessionMetrics,
)

from models import (
    TaskRequest,
    TaskResponse,
    TaskStatus,
    SaveWorkflowRequest,
    SaveStaticDataRequest,
    ActionStep,
    WorkflowRecord,
    SessionContext,
    # Semantic QA Execution models
    TestPlan,
    TestStep,
    TestPlanExecutionRequest,
    TestPlanExecutionResult,
    TestPlanExecutionStatus,
    StepExecutionResult,
    StepStatus,
    SemanticActionType,
)
from agent import ComputerUseAgent
from browser import BrowserController
from semantic_qa_agent import SemanticQAAgent, create_semantic_qa_agent, validate_test_plan
from core.test_plan_parser import TestPlanParser
from storage import save_workflow, load_workflow, list_workflows, delete_workflow
from pinecone_service import PineconeService, IndexType
from download_tracker import get_download_tracker
from hammer_indexer import get_hammer_indexer
from goal_decomposer import get_goal_decomposer, SubTask
from hammer_downloader import (
    get_hammer_downloader, 
    is_hammer_download_intent, 
    extract_company_from_goal,
    parse_companies_from_text
)
from auth_service import get_auth_service
from dependency_analyzer import get_dependency_analyzer
import os

# Initialize services
pinecone_service = PineconeService()


# Store active tasks
active_tasks: Dict[str, Dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("app_starting", version="1.0.0")
    
    # LAZY AUTH: Authentication is now triggered on-demand when:
    # 1. User downloads a Hammer file (needs API access)
    # 2. User clicks "Start Browser Testing" (needs browser auth)
    # This reduces startup time and resource usage
    print("[STARTUP] Lazy auth enabled - authentication will happen on-demand")
        
    yield
    logger.info("app_shutting_down")


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

# Prometheus HTTP metrics instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== AUTHENTICATION ENDPOINTS ====================

class GoogleAuthRequest(BaseModel):
    """Request model for Google OAuth login."""
    id_token: str


class AuthResponse(BaseModel):
    """Response model for authentication."""
    token: str
    user: dict


@app.post("/auth/google", response_model=AuthResponse)
async def auth_google(request: GoogleAuthRequest):
    """
    Authenticate with Google OAuth.
    
    Receives Google ID token from frontend, verifies with Google,
    validates email domain (@graphiteconnect.com only), and returns
    a session JWT for subsequent requests.
    """
    auth_service = get_google_auth_service()
    
    # Verify Google token and check domain
    user_info = auth_service.verify_google_token(request.id_token)
    
    # Create internal session token
    session_token = auth_service.create_session_token(user_info)
    
    return AuthResponse(
        token=session_token,
        user={
            "email": user_info["email"],
            "name": user_info["name"],
            "picture": user_info["picture"],
        }
    )


@app.get("/auth/verify")
async def auth_verify(current_user: dict = Depends(get_current_user)):
    """
    Verify current session token and return user info.
    
    Use this endpoint to check if user is still authenticated
    and to get current user details.
    """
    return {
        "authenticated": True,
        "user": current_user,
    }


@app.post("/auth/logout")
async def auth_logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint (for future server-side session invalidation).
    
    Currently just acknowledges logout - token invalidation happens
    client-side by removing from localStorage.
    """
    print(f"[AUTH] User logged out: {current_user.get('email', 'unknown')}")
    return {"status": "logged_out"}


class GraphiteAuthResponse(BaseModel):
    """Response model for Graphite authentication."""
    status: str
    cached: bool
    jwt_available: bool
    cookies_count: int


@app.post("/auth/graphite/init", response_model=GraphiteAuthResponse)
async def init_graphite_auth(current_user: dict = Depends(get_current_user_optional)):
    """
    Initialize Graphite authentication on-demand (lazy auth).
    
    This endpoint is called when:
    1. User downloads a Hammer file (needs API access)
    2. User clicks "Start Browser Testing" (needs browser auth)
    
    Returns cached auth if already authenticated, otherwise performs login.
    """
    auth_service = get_auth_service()
    
    # Check if already authenticated
    existing_jwt = auth_service.get_jwt_token()
    existing_cookies = auth_service.get_cookies_dict()
    
    if existing_jwt or existing_cookies:
        print(f"[LAZY AUTH] Using cached auth (JWT: {bool(existing_jwt)}, Cookies: {len(existing_cookies)})")
        return GraphiteAuthResponse(
            status="already_authenticated",
            cached=True,
            jwt_available=bool(existing_jwt),
            cookies_count=len(existing_cookies)
        )
    
    # Perform login
    print("[LAZY AUTH] No cached auth found, performing login...")
    try:
        await auth_service.login_and_capture_state()
        
        jwt_token = auth_service.get_jwt_token()
        cookies = auth_service.get_cookies_dict()
        
        if jwt_token or cookies:
            print(f"[LAZY AUTH] ✅ Auth successful (JWT: {bool(jwt_token)}, Cookies: {len(cookies)})")
            return GraphiteAuthResponse(
                status="authenticated",
                cached=False,
                jwt_available=bool(jwt_token),
                cookies_count=len(cookies)
            )
        else:
            print("[LAZY AUTH] ⚠️ Auth completed but no credentials captured")
            raise HTTPException(status_code=401, detail="Authentication failed - no credentials captured")
            
    except Exception as e:
        print(f"[LAZY AUTH] ❌ Auth failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


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
    """Save a task's steps as a reusable workflow and index in Pinecone.
    
    Supports two modes:
    1. Frontend sends accumulated steps directly (request.steps) - PREFERRED
    2. Fallback to active_tasks[task_id] for backwards compatibility
    """
    # Use accumulated steps from frontend if provided, otherwise fallback to active_tasks
    if request.steps and len(request.steps) > 0:
        # Frontend sent accumulated steps directly
        workflow_steps = request.steps
        logger.info("workflow_save_started", step_count=len(workflow_steps), source="frontend")
    elif request.task_id in active_tasks:
        # Fallback to task-specific steps
        task_data = active_tasks[request.task_id]
        workflow_steps = task_data.get("steps", [])
        logger.info("workflow_save_started", step_count=len(workflow_steps), source="active_task", task_id=request.task_id)
    else:
        raise HTTPException(status_code=404, detail="No steps found - provide steps in request or valid task_id")
    
    # Extract category from tags (first tag is the category)
    category = request.tags[0] if request.tags else "steps"
    
    workflow = WorkflowRecord(
        id=request.task_id,
        name=request.name,
        description=request.description,
        steps=workflow_steps,
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
        print(f"[OK] Generated execution summary for '{workflow.name}'")
        print(f"[SUMMARY] Summary preview:\n{execution_summary[:500]}...")
    except Exception as e:
        print(f"[WARNING] Failed to generate workflow summary: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Index in Pinecone with BOTH raw steps AND execution summary
    pinecone_indexed = False
    try:
        # Generate embedding using Unified Embedder (Gemini)
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        
        text_to_embed = f"{workflow.name}: {workflow.description}"
        embedding = embedder.embed_query(text_to_embed)
        
        # Upsert to steps-index with execution_summary
        # Get last step info for additional context
        last_step = workflow.steps[-1] if workflow.steps else None
        last_step_description = None
        last_step_image_description = None
        
        if last_step:
            last_step_description = last_step.reasoning or f"{last_step.action_type} at {last_step.url}"
            
            # Generate AI description of the last screenshot (instead of useless local path)
            if last_step.screenshot_path:
                try:
                    from pathlib import Path
                    from google import genai
                    from google.genai import types
                    import base64
                    
                    screenshot_path = Path(last_step.screenshot_path)
                    if screenshot_path.exists():
                        # Read screenshot and generate description
                        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
                        
                        with open(screenshot_path, "rb") as f:
                            image_bytes = f.read()
                        image_b64 = base64.b64encode(image_bytes).decode()
                        
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=[
                                types.Content(
                                    role="user",
                                    parts=[
                                        types.Part(text="Describe this screenshot in 1-2 sentences. Focus on what page/screen it shows and any important UI elements visible. Be concise."),
                                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                    ]
                                )
                            ],
                            config=types.GenerateContentConfig(
                                temperature=0.1,
                                max_output_tokens=150,
                            )
                        )
                        
                        if response and response.candidates:
                            last_step_image_description = response.text.strip()
                            print(f"Generated image description: {last_step_image_description[:100]}...")
                except Exception as img_err:
                    print(f"Could not generate image description: {img_err}")
                    last_step_image_description = f"Screenshot of {last_step.url or 'unknown page'}"
        
        
        # Upsert with enhanced format (SINGLE SOURCE OF TRUTH)
        # We no longer use the legacy upsert_step which created duplicate records
        if request.text or request.urls_visited or request.steps_reference_only:
            enhanced_record_id = pinecone_service.upsert_workflow_record(
                workflow_id=workflow.id,
                name=workflow.name,
                description=workflow.description,
                embedding=embedding,
                namespace=request.namespace,
                index_name=request.index,
                text=request.text,
                urls_visited=request.urls_visited,
                actions_performed=request.actions_performed,
                steps_reference_only=request.steps_reference_only,
                tags=workflow.tags,
                extra_metadata={
                    "execution_summary": execution_summary,
                    "step_count": len(workflow.steps),
                    "last_step_description": last_step_description,
                    "last_step_image_description": last_step_image_description,
                },
                user_prompts=request.user_prompts  # User chat messages
            )
            pinecone_indexed = True
            print(f"[ENHANCED] Workflow indexed to {request.index}/{request.namespace}")
    except Exception as e:
        print(f"[WARNING] Failed to index workflow in Pinecone: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        "status": "saved",
        "id": workflow.id,
        "path": filepath,
        "category": category,
        "pinecone_indexed": pinecone_indexed,
        "has_summary": execution_summary is not None,
    }


# ==================== SUCCESS CASES ENDPOINTS ====================

class SaveSuccessCaseRequest(BaseModel):
    """Request model for saving a success case."""
    goal_text: str
    workflow_name: str
    steps: List[Dict]
    final_url: str = ""
    company_context: str = ""
    session_id: str = ""
    execution_time_ms: int = 0


@app.post("/success-cases")
async def save_success_case(request: SaveSuccessCaseRequest):
    """Save a successful workflow execution for reinforcement learning."""
    try:
        # Generate embedding from goal text
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        embedding = embedder.embed_query(request.goal_text)
        
        # Generate workflow_id from hash of goal
        import hashlib
        workflow_id = hashlib.md5(f"{request.goal_text}:{request.workflow_name}".encode()).hexdigest()[:16]
        
        # Store success case
        vector_id = pinecone_service.upsert_success_case(
            goal_text=request.goal_text,
            workflow_id=workflow_id,
            workflow_name=request.workflow_name,
            steps=request.steps,
            embedding=embedding,
            final_url=request.final_url,
            company_context=request.company_context,
            session_id=request.session_id,
            execution_time_ms=request.execution_time_ms,
        )
        
        return {
            "status": "saved",
            "id": vector_id,
            "workflow_id": workflow_id,
            "step_count": len(request.steps),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save success case: {str(e)}")


@app.get("/success-cases/search")
async def search_success_cases(query: str, top_k: int = 5, company: str = None):
    """Search for similar successful executions."""
    try:
        # Generate embedding from query
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        embedding = embedder.embed_query(query)
        
        # Search
        results = pinecone_service.find_similar_success_cases(
            query_embedding=embedding,
            top_k=top_k,
            company_filter=company,
        )
        
        return {
            "query": query,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/success-cases/stats")
async def get_success_cases_stats():
    """Get statistics for the success cases index."""
    return pinecone_service.get_success_cases_stats()


# ==================== STATIC DATA ENDPOINTS ====================

@app.post("/static-data")
async def save_static_data(request: SaveStaticDataRequest):
    """Save static data to the static_data namespace.
    
    This endpoint stores valuable information that rarely changes
    (credentials, API keys, configuration values, reference data).
    
    Security:
    - Input is sanitized server-side to prevent injection attacks
    - HTML/JS tags are stripped using bleach
    - Dangerous patterns (eval, exec, $where, etc.) are rejected
    - Maximum 10,000 characters allowed
    """
    if not request.data or not request.data.strip():
        raise HTTPException(status_code=400, detail="Data field is required and cannot be empty")
    
    try:
        # Generate embedding for the data
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        embedding = embedder.embed_query(request.data)
        
        # Store in Pinecone (sanitization happens inside upsert_static_data)
        vector_id = pinecone_service.upsert_static_data(
            data=request.data,
            embedding=embedding
        )
        
        return {
            "status": "saved",
            "id": vector_id,
            "char_count": len(request.data),
            "namespace": "static_data",
        }
        
    except ValueError as ve:
        # Security validation failed (dangerous pattern detected)
        raise HTTPException(status_code=400, detail=f"Security validation failed: {str(ve)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save static data: {str(e)}")


@app.get("/static-data")
async def get_all_static_data(limit: int = 20):
    """Get all static data records."""
    try:
        records = pinecone_service.find_all_static_data(limit=limit)
        return {
            "count": len(records),
            "records": records,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve static data: {str(e)}")


# ==================== COMPANIES & HAMMER DOWNLOAD ENDPOINTS ====================

@app.get("/companies")
async def list_companies():
    """List all available companies for hammer download."""
    return {
        "companies": [
            {
                "id": c["id"],
                "name": c["company_name"],
                "aliases": c.get("aliases", [])
            }
            for c in COMPANIES
        ],
        "count": len(COMPANIES),
    }


@app.get("/companies/search")
async def search_companies(q: str):
    """
    Search for a company by name or alias (fuzzy match).
    
    Args:
        q: Search query (e.g., "western", "adobe")
    """
    # Inject auth token if available
    auth_service = get_auth_service()
    cookies = auth_service.get_cookies_dict()
    cookie_str = "; ".join([f"{k}={v}" for k,v in cookies.items()])
    
    downloader = get_hammer_downloader(auth_cookie=cookie_str)
    match = downloader.find_company(q)
    
    if match:
        return {
            "found": True,
            "company": {
                "id": match["id"],
                "name": match["company_name"],
                "aliases": match.get("aliases", [])
            }
        }
    else:
        return {
            "found": False,
            "query": q,
            "available": [c["company_name"] for c in COMPANIES]
        }


class HammerDownloadRequest(BaseModel):
    """Request model for hammer download."""
    company: str  # Company name, ID, or alias
    clear_existing: bool = True  # Clear hammer-index before indexing
    auth_cookie: Optional[str] = None  # Optional auth cookie override


@app.post("/hammer/download")
async def download_hammer_direct(
    request: HammerDownloadRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Download and index a hammer file directly via Graphite API.
    
    This bypasses browser automation and directly calls the Graphite
    history API to fetch the latest hammer file for a company.
    
    Multi-user support: Uses user's namespace for isolation.
    
    Args:
        company: Company name, ID, or alias (e.g., "western", "US66254")
        clear_existing: If True, clear hammer-index before indexing
        auth_cookie: Optional authentication cookie
    """
    try:
        # Get user ID for namespace isolation
        user_id = None
        if current_user:
            user_id = current_user.get("sub") or current_user.get("email")
            print(f"[HAMMER] Indexing for user: {user_id}")
        else:
            print("[HAMMER] Warning: No authenticated user, using default namespace")
        
        # Get auth credentials - prioritize JWT token over cookies
        auth_cookie = request.auth_cookie
        jwt_token = None
        
        if not auth_cookie:
            auth_service = get_auth_service()
            
            # First try to get JWT token (preferred)
            jwt_token = auth_service.get_jwt_token()
            
            # If no JWT, try to get cookies as fallback
            if not jwt_token:
                cookies = auth_service.get_cookies_dict()
                
                # If neither available, trigger login
                if not cookies:
                    print("[HAMMER] No cached auth, triggering login...")
                    await auth_service.login_and_capture_state()
                    jwt_token = auth_service.get_jwt_token()
                    cookies = auth_service.get_cookies_dict()
                
                if not jwt_token and cookies:
                    auth_cookie = "; ".join([f"{k}={v}" for k,v in cookies.items()])
                    print(f"[HAMMER] Using {len(cookies)} auth cookies (fallback)")
            
            if jwt_token:
                print(f"[HAMMER] Using JWT token ({len(jwt_token)} chars)")
            elif not auth_cookie:
                print("[HAMMER] Warning: No auth credentials available, API calls may fail")
        
        downloader = get_hammer_downloader(auth_cookie=auth_cookie, jwt_token=jwt_token)
        
        # Run the download and index pipeline with user_id for namespace
        result = await downloader.download_and_index(
            company_query=request.company,
            clear_existing=request.clear_existing,
            user_id=user_id  # Pass user_id for namespace isolation
        )
        
        if result.get("success"):
            return {
                "status": "success",
                "message": f"Hammer indexed successfully for {result.get('company_name')}",
                "details": result,
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Download failed")
            )
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Hammer download failed: {str(e)}")


@app.get("/hammer/metadata")
async def get_hammer_metadata(current_user: dict = Depends(get_current_user_optional)):
    """
    Get metadata about the currently indexed hammer for the user.
    
    Returns company name, ID, indexed date, and Jira label match.
    Use this to display hammer info in the UI header.
    """
    from session_service import get_session_service
    
    session_service = get_session_service()
    
    if not current_user:
        return {
            "indexed": False,
            "message": "No authenticated user"
        }
    
    user_id = current_user.get("sub") or current_user.get("email")
    
    if not user_id:
        return {
            "indexed": False,
            "message": "Could not determine user ID"
        }
    
    metadata = session_service.get_company_metadata(user_id)
    
    if metadata:
        return {
            "indexed": True,
            "company_id": metadata.company_id,
            "company_name": metadata.company_name,
            "indexed_at": metadata.indexed_at,
            "hammer_filename": metadata.hammer_filename,
            "jira_label": metadata.jira_label,
            "record_count": metadata.record_count,
            "namespace": session_service.get_user_namespace(user_id)
        }
    else:
        return {
            "indexed": False,
            "message": "No hammer indexed for this user"
        }


@app.get("/hammer/download/status/{company_id}")
async def get_hammer_download_status(company_id: str):
    """
    Get the current hammer index status for a company.
    
    Args:
        company_id: The company ID (e.g., "US66254")
    """
    try:
        # Get hammer index stats
        stats = pinecone_service.get_hammer_stats()
        
        # Try to find latest hammer history for this company
        downloader = get_hammer_downloader()
        latest = await downloader.get_latest_hammer_id(company_id)
        
        return {
            "company_id": company_id,
            "index_stats": stats,
            "has_data": stats.get("total_vector_count", 0) > 0,
            "latest_available": {
                "id": latest.get("_id") if latest else None,
                "filename": latest.get("originalFilename") if latest else None,
                "uploaded_at": latest.get("createdAt") if latest else None,
                "uploaded_by": latest.get("user") if latest else None,
            } if latest else None,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hammer/index-workflow")
async def index_hammer_workflow_endpoint():
    """
    Index the Hammer Download workflow into Pinecone's steps-index.
    
    This teaches the agent that when users request hammer downloads,
    it should use the direct API method instead of browser automation.
    
    Run this ONCE after starting the backend.
    """
    try:
        # Define the workflow
        workflow_data = {
            "id": "workflow_hammer_download_direct",
            "name": "Download Hammer File (Direct API)",
            "description": "Download hammer file from a client using direct API calls. IMPORTANT: This does NOT require browser navigation - use the HammerDownloader API directly.",
            "category": "hammer",
            "tags": ["hammer", "download", "api", "index", "xlsm", "western", "digital"],
            "step_count": 1,
            "execution_type": "direct_api",
            "requires_browser": False,  # Critical: tells decomposer to not use browser
            "execution_summary": """
CRITICAL: This workflow uses DIRECT API CALLS, not browser automation!

When user requests to download a hammer file from a company:
1. DO NOT search the web or navigate anywhere
2. The system automatically calls HammerDownloader.download_and_index()
3. The hammer file is downloaded via Graphite API and indexed to Pinecone

TRIGGER PHRASES:
- "download hammer from [company]"
- "get hammer file from [company]"
- "descargar hammer de [company]"
- "download western digital hammer"

COMPANIES: Western Digital (US66254), Adobe-TEST (US1229), Vonage (US5078)

THIS IS AUTOMATIC - NO BROWSER ACTIONS NEEDED!
""",
        }
        
        # Generate embedding
        text_to_embed = """
        download hammer file from company client western digital adobe vonage
        descargar hammer archivo xlsm de cliente
        get hammer configuration download automatically api
        fetch hammer from graphite no browser needed direct api call
        """
        
        # Generate embedding
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        embedding = embedder.embed_query(text_to_embed)
        
        # Upsert main workflow
        pinecone_service.upsert_step(
            action_type="hammer_download",
            goal_description="Download Hammer File from Company (Direct API)",
            step_details=workflow_data,
            embedding=embedding,
            efficiency_score=1.0,
        )
        
        # Also add company-specific variations
        variations = [
            ("Download hammer from Western Digital", "download hammer western digital wd US66254 xlsm"),
            ("Descargar hammer de cliente", "descargar hammer archivo cliente company download spanish"),
            ("Download hammer to test configuration", "download hammer test new configuration verify changes"),
        ]
        
        for goal, text in variations:
            emb = embedder.embed_query(text)
            
            pinecone_service.upsert_step(
                action_type="hammer_download",
                goal_description=goal,
                step_details={
                    "id": f"workflow_hammer_{goal.lower().replace(' ', '_')[:30]}",
                    "name": goal,
                    "execution_type": "direct_api",
                    "requires_browser": False,
                    "parent_workflow": "workflow_hammer_download_direct",
                },
                embedding=emb,
                efficiency_score=1.0,
            )
        
        # Verify it was indexed
        test_query = "download hammer from western digital"
        test_emb = embedder.embed_query(test_query)
        
        matches = pinecone_service.find_similar_steps(test_emb, top_k=3)
        
        return {
            "status": "success",
            "message": "Hammer download workflow indexed to Pinecone",
            "workflows_indexed": 1 + len(variations),
            "verification": {
                "test_query": test_query,
                "matches": [
                    {"goal": m.get("goal_description", "N/A"), "score": m.get("score", 0)}
                    for m in matches[:3]
                ]
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to index workflow: {str(e)}")


@app.websocket("/ws")
@app.websocket("/ws/agent")
@app.websocket("/ws/training")
async def websocket_endpoint(websocket: WebSocket):
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
    connection_start = time.time()
    WEBSOCKET_CONNECTIONS.inc()
    
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
    
    # ==============================================
    # SESSION METRICS - Real-time tracking for UI
    # ==============================================
    session_metrics = SessionMetrics(session_id=session_context.session_id)
    
    # Bind session context for structured logging
    bind_context(session_id=session_context.session_id, trace_id=generate_trace_id())
    logger.info("websocket_connected", remote=str(websocket.client))

    async def send_json(data: dict, include_metrics: bool = True):
        """Helper to send JSON message, optionally including session metrics."""
        try:
            await websocket.send_text(json.dumps(data))
            WEBSOCKET_MESSAGES.labels(direction="sent", message_type=data.get("type", "unknown")).inc()
            session_metrics.record_message_sent()
            
            # Send metrics update after key events (not for metrics messages themselves)
            if include_metrics and data.get("type") in ("step", "completed", "error", "status"):
                await websocket.send_text(json.dumps({
                    "type": "metrics",
                    "data": session_metrics.to_dict()
                }))
        except Exception as e:
            logger.warning("websocket_send_error", error=str(e))

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
                session_metrics.record_message_received()

                if msg_type == "start" or msg_type == "task":
                    goal = message.get("goal", "")
                    start_url = message.get("start_url", "")
                    step_offset = message.get("step_offset", 0)
                    mode = message.get("mode", "training") # "training" or "production"

                    if not goal:
                        await send_json({"type": "error", "message": "Goal is required"})
                        continue

                    # ==============================================
                    # DETECT TEST PLAN JSON IN GOAL
                    # ==============================================
                    test_plan_detected = None
                    try:
                        # Try to parse as JSON test plan
                        if goal.strip().startswith("{"):
                            parsed = json.loads(goal)
                            # Check if it looks like a test plan
                            if "test_case_id" in parsed and "steps" in parsed:
                                test_plan_detected = parsed
                                print(f"[TEST PLAN] Detected test plan: {parsed.get('test_case_id')}")
                            elif "test_plan" in parsed:
                                test_plan_detected = parsed.get("test_plan")
                                print(f"[TEST PLAN] Detected wrapped test plan: {test_plan_detected.get('test_case_id')}")
                    except json.JSONDecodeError:
                        pass  # Not JSON, treat as regular goal

                    # If test plan detected, run Semantic QA Agent
                    if test_plan_detected:
                        await send_json({
                            "type": "status",
                            "status": "running",
                            "message": f"Executing Test Plan: {test_plan_detected.get('test_case_id', 'Unknown')}"
                        })

                        task_id = str(uuid.uuid4())

                        # Create persistent browser if not exists
                        if persistent_browser is None:
                            persistent_browser = BrowserController()
                            auth_service = get_auth_service()
                            storage_state = auth_service.get_storage_state()
                            await persistent_browser.start(storage_state=storage_state)

                        # Create Semantic QA Agent
                        semantic_agent = SemanticQAAgent(
                            browser=persistent_browser,
                            session_metrics=session_metrics
                        )

                        async def run_test_plan_task():
                            try:
                                result = await semantic_agent.execute_test_plan(
                                    test_plan_detected,
                                    stop_on_failure=True,
                                    max_retries_per_step=3
                                )

                                # Send step results
                                for step_result in result.steps_results:
                                    status_emoji = "✓" if step_result.status == "pass" else "✗" if step_result.status == "fail" else "○"
                                    await send_json({
                                        "type": "message",
                                        "role": "agent",
                                        "content": f"{status_emoji} Step {step_result.step_id} ({step_result.action}): {step_result.status.upper()}"
                                    })

                                # Send final result
                                summary = f"### Test Execution Complete\n\n"
                                summary += f"**Test Case:** {result.test_case_id}\n"
                                summary += f"**Status:** {result.overall_status.upper()}\n"
                                summary += f"**Passed:** {result.passed_steps} | **Failed:** {result.failed_steps} | **Skipped:** {result.skipped_steps}\n"
                                summary += f"**Duration:** {result.total_execution_time_ms}ms"

                                await send_json({
                                    "type": "status",
                                    "status": "completed",
                                    "message": summary
                                })

                                await send_json({
                                    "type": "completed",
                                    "workflow_id": task_id,
                                    "test_result": result.model_dump()
                                })

                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                await send_json({
                                    "type": "error",
                                    "message": f"Test plan execution failed: {str(e)}"
                                })

                        agent_task = asyncio.create_task(run_test_plan_task())
                        continue  # Skip regular goal processing

                    # Inject Auth State
                    auth_service = get_auth_service()
                    storage_state = auth_service.get_storage_state()
                    if storage_state:
                         print("[WS] Injecting auth state into browser session")
                         # Note: BrowserController needs to support this in .start()
                         
                    # Determine route path to set default mode if not specified
                    # (FastAPI doesn't easily expose path in WS, so rely on client 'mode' or default)
                    
                    # Store mode in context
                    active_tasks[str(uuid.uuid4())] = {"mode": mode, "status": "pending"} # placeholder
                    
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
                        print(f"[CLIPBOARD] USER MANUALLY SET CLIPBOARD: {value_to_remember}")
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
                        print(f"[NOTE] USER STORED NOTE: {key} = {value}")
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
                    active_tasks[task_id] = {"steps": [], "status": TaskStatus.PENDING, "mode": mode}
                    session_metrics.record_task_started()
                    
                    # --- PRODUCTION MODE: ADVISOR ---
                    if mode == "production":
                        await send_json({
                            "type": "status",
                            "status": "thinking",
                            "message": "Analyzing Ticket & Hammer Dependencies...",
                            "task_id": task_id
                        })
                        
                        try:
                            # Run Dependency Analysis
                            analyzer = get_dependency_analyzer()
                            analysis = await analyzer.analyze_ticket(goal)
                            
                            # Send Report
                            report_text = f"### 🛡️ Production Advisor Report\n\n"
                            
                            if analysis["found"]:
                                report_text += f"{analysis['guidance_text']}\n\n"
                                report_text += "### 📋 Recommended Verification Steps\n"
                                for q in analysis["questions_to_verify"]:
                                    report_text += f"- [ ] Check {q}\n"
                                    
                                report_text += "\n> **Next Step:** Please manually verify these settings in the Hammer file or Environment before proceeding."
                            else:
                                report_text += "No direct Hammer dependencies found for this ticket. Proceed with standard exploratory testing."
                                
                            # Send as a 'step' with no screenshot, just text/plan
                            # We treat it as an agent message
                            await send_json({
                                "type": "status",
                                "status": "completed",
                                "message": report_text, 
                                "task_id": task_id
                            })
                            
                            # Also save as a pseudo-task result so it's not empty
                            active_tasks[task_id]["analysis"] = analysis
                            
                        except Exception as e:
                            logger.error("analysis_failed", error=str(e))
                            await send_json({
                                "type": "error", 
                                "message": f"Dependency Analysis Failed: {str(e)}",
                                "task_id": task_id
                            })
                            
                        continue  # End this loop iteration, don't start the standard agent
                    
                    # --- TRAINING MODE: STANDARD AGENT ---

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
                        session_metrics.record_agent_turn()  # Track each agent step
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
                            "task_id": task_id
                        }))

                    # Create persistent browser if not exists
                    if persistent_browser is None:
                        persistent_browser = BrowserController()
                        
                        # Inject Auth State from Service
                        auth_service = get_auth_service()
                        storage_state = auth_service.get_storage_state()
                        if storage_state:
                            print("[WS] Starting browser with injected auth state")
                        
                        # Start browser explicitly to inject auth
                        await persistent_browser.start(start_url, storage_state=storage_state)
                        # NOTE: Changed from google.com to about:blank - no more unnecessary searches!
                        print(f"[BROWSER] Browser started at: {start_url or 'about:blank'}")
                    
                    # Create agent with PERSISTENT browser AND session context
                    # The session_context is passed in - it lives across all tasks!
                    agent = ComputerUseAgent(
                        on_step=on_step,
                        on_status_change=on_status_change,
                        browser=persistent_browser,
                        session_context=session_context,  # <-- THE KEY TO MEMORY!
                        session_metrics=session_metrics,  # <-- REAL-TIME METRICS!
                    )
                    print(f"🤖 Agent created with session context: {session_context.session_id}")



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
                    
                    # ==============================================
                    # HAMMER DOWNLOAD DETECTION - BYPASS BROWSER!
                    # Uses browser cookies for authenticated API calls
                    # ==============================================
                    if is_hammer_download_intent(goal):
                        print(f"\n[HAMMER] HAMMER DOWNLOAD DETECTED - USING DIRECT API!")
                        company = extract_company_from_goal(goal)
                        
                        if company:
                            await send_json({
                                "type": "status",
                                "status": "running",
                                "message": f"Downloading hammer from {company} via API...",
                                "task_id": task_id
                            })
                            
                            try:
                                # Extract cookies from browser session for authenticated API calls
                                auth_cookie = None
                                if persistent_browser and persistent_browser.is_started:
                                    auth_cookie = await persistent_browser.get_auth_cookies_header()
                                    if auth_cookie:
                                        print(f"[AUTH] Using browser session cookies for API auth")
                                        print(f"[AUTH] Cookie length: {len(auth_cookie)} chars")
                                    else:
                                        print(f"[AUTH] WARNING: No cookies found - API may return 401")
                                        print(f"[AUTH] Make sure to login first before downloading hammer!")
                                else:
                                    print(f"[AUTH] WARNING: No browser session - please login first!")
                                    await send_json({
                                        "type": "error",
                                        "message": "Please login first before downloading hammer files"
                                    })
                                    continue
                                
                                
                                # Fetch company registry from static_data namespace
                                print(f"[HAMMER] Fetching company registry from static_data...")
                                companies_list = []
                                try:
                                    static_records = pinecone_service.find_all_static_data(limit=10)
                                    for record in static_records:
                                        data = record.get("data", "")
                                        if data:
                                            try:
                                                parsed = json.loads(data) if isinstance(data, str) else data
                                                if isinstance(parsed, list):
                                                    # Each item should have company_name, id, etc.
                                                    companies_list.extend(parsed)
                                            except json.JSONDecodeError:
                                                pass  # Skip non-JSON records
                                    
                                    if companies_list:
                                        print(f"[HAMMER] Loaded {len(companies_list)} companies from static_data")
                                    else:
                                        print("[HAMMER] WARNING: No companies found in static_data namespace")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Failed to load company registry from static_data: {e}")

                                # Create downloader with browser cookies AND dynamic companies list
                                downloader = get_hammer_downloader(auth_cookie=auth_cookie, companies=companies_list)
                                result = await downloader.download_and_index(company)
                                
                                if result.get("success"):
                                    await send_json({
                                        "type": "status",
                                        "status": "completed",
                                        "message": f"Hammer indexed: {result.get('records_count', 0)} records from {result.get('company_name')}"
                                    })
                                    await send_json({
                                        "type": "completed",
                                        "workflow_id": task_id,
                                        "step_count": 1,
                                        "hammer_result": result
                                    })
                                    
                                    # Update session context
                                    session_context.important_notes["hammer_company"] = result.get("company_name")
                                    session_context.important_notes["hammer_records"] = str(result.get("records_count", 0))
                                    session_context.important_notes["hammer_file"] = result.get("filename", "")
                                else:
                                    error_msg = result.get("error", "Unknown error")
                                    # Check if it's an auth error
                                    if "401" in str(error_msg) or "Unauthorized" in str(error_msg):
                                        error_msg = "Authentication failed. Please login to Graphite first, then try downloading again."
                                    await send_json({
                                        "type": "error",
                                        "message": f"Hammer download failed: {error_msg}"
                                    })
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                await send_json({
                                    "type": "error",
                                    "message": f"Hammer download error: {str(e)}"
                                })
                            
                            continue  # Skip agent execution - hammer is done!
                        else:
                            # Could not extract company, let agent try
                            print(f"[HAMMER] Could not extract company from goal, falling back to agent")
                    
                    if is_simple_navigation:
                        print(f"[NAV] Simple URL navigation detected - skipping decomposition")
                    else:
                        try:
                            # Initialize goal decomposer with Pinecone service
                            decomposer = get_goal_decomposer(pinecone_service)
                            
                            # Check if goal contains multiple tasks
                            execution_plan = decomposer.get_execution_plan(goal)
                            
                            print(f"\n[DECOMP] GOAL DECOMPOSITION RESULT:")
                            print(f"   Original goal: {goal}")
                            print(f"   Decomposed: {execution_plan['is_decomposed']}")
                            print(f"   Sub-tasks: {execution_plan['subtask_count']}")
                            
                            if execution_plan['is_decomposed'] and execution_plan['subtask_count'] > 1:
                                # Multiple sub-tasks detected
                                print(f"[PLAN] EXECUTING {execution_plan['subtask_count']} SUB-TASKS SEQUENTIALLY:")
                                
                                for i, subtask in enumerate(execution_plan['subtasks'], 1):
                                    print(f"   {i}. {subtask.action}: {subtask.target}")
                                    if subtask.workflow_match:
                                        print(f"      [OK] Matched workflow: {subtask.workflow_match.get('goal_description', 'N/A')}")
                                
                                subtasks_to_execute = execution_plan['subtasks']
                                
                                # Notify frontend
                                await send_json({
                                    "type": "status", 
                                    "status": "planning",
                                    "message": f"Decomposed into {len(subtasks_to_execute)} tasks: {', '.join([st.action for st in subtasks_to_execute])}"
                                })
                            else:
                                # Single task - try to match workflow directly
                                print(f"[PLAN] Single task detected, searching workflow...")
                                
                                # Generate embedding
                                # Generate embedding
                                from screenshot_embedder import get_embedder
                                embedder = get_embedder()
                                embedding = embedder.embed_query(goal)
                                
                                # Extract keywords from goal for fallback
                                keywords = decomposer._extract_keywords(goal)
                                
                                # Search matches with TIERED thresholds
                                matches = pinecone_service.find_similar_steps(embedding, top_k=3, namespace="test_execution_steps")
                                print(f"[DEBUG] DEBUG: Raw matches found: {[(m.get('goal_description'), m.get('score')) for m in matches]}")
                                
                                # Use tiered matching with keyword fallback
                                best_match = pinecone_service.get_best_step_for_goal_tiered(
                                    embedding, 
                                    keywords=keywords,
                                    namespace="test_execution_steps"
                                )
                                
                                if best_match:
                                    # ==============================================
                                    # CHECK FORMAT: JSON_V2 (clean JSON) vs TEXT (old) vs LEGACY (step_details)
                                    # ==============================================
                                    if best_match.get("format") == "json_v2":
                                        # JSON_V2 FORMAT - new clean format with JSON strings
                                        print(f"[JSON_V2 FORMAT] Found workflow (score: {best_match.get('score', 'N/A')})")
                                        recommended_workflow = {
                                            "name": f"Previous: {goal}",
                                            "format": "json_v2",
                                            "urls_visited": best_match.get("urls_visited", "[]"),
                                            "actions": best_match.get("actions", "{}"),
                                            "steps": best_match.get("steps", "[]"),
                                            "user_prompts": best_match.get("user_prompts", "[]"),
                                        }
                                        workflow_name = recommended_workflow["name"]
                                        
                                        print(f"[OK] Context Loaded from JSON_V2 FORMAT workflow")
                                        print(f"   URLs: {best_match.get('urls_visited', '')[:100]}...")
                                        
                                        await send_json({
                                            "type": "status", 
                                            "status": "planning",
                                            "message": f"Found similar workflow (score: {best_match.get('score', 0):.2f})",
                                            "task_id": task_id
                                        })
                                    elif best_match.get("user_prompts") or best_match.get("system_logs"):
                                        # OLD TEXT FORMAT - test_execution_steps namespace
                                        print(f"[TEXT FORMAT] Found workflow with system_logs (score: {best_match.get('score', 'N/A')})")
                                        recommended_workflow = {
                                            "name": f"Previous: {goal}",
                                            "format": "new",
                                            "urls_visited": best_match.get("urls_visited", ""),
                                            "actions_performed": best_match.get("actions_performed", ""),
                                            "system_logs": best_match.get("system_logs", ""),
                                            "user_prompts": best_match.get("user_prompts", ""),
                                        }
                                        workflow_name = recommended_workflow["name"]
                                        
                                        # Show preview of what was found
                                        print(f"[OK] Context Loaded from TEXT FORMAT workflow")
                                        print(f"   URLs visited: {best_match.get('urls_visited', '')[:200]}...")
                                        print(f"   Actions: {best_match.get('actions_performed', '')[:200]}...")
                                        
                                        await send_json({
                                            "type": "status", 
                                            "status": "planning",
                                            "message": f"Found similar workflow (score: {best_match.get('score', 0):.2f})",
                                            "task_id": task_id
                                        })
                                    else:
                                        # OLD FORMAT - parse step_details JSON
                                        print(f"[OLD FORMAT] Found workflow match: {best_match.get('goal_description')} (score: {best_match.get('score', 'N/A')})")
                                        raw_details = best_match.get("step_details", "{}")
                                        
                                        # Handle case where it might be already dict or string
                                        if isinstance(raw_details, str):
                                            try:
                                                recommended_workflow = json.loads(raw_details)
                                            except:
                                                try:
                                                    import ast
                                                    recommended_workflow = ast.literal_eval(raw_details)
                                                    print("[DEBUG] Successfully parsed workflow using ast.literal_eval (legacy format)")
                                                except Exception as e:
                                                    print(f"[WARNING] Failed to parse workflow details: {e}")
                                                    pass
                                        elif isinstance(raw_details, dict):
                                            recommended_workflow = raw_details

                                        if recommended_workflow:
                                            workflow_name = recommended_workflow.get("name") or best_match.get("workflow_name") or "Previous Run"
                                            steps = recommended_workflow.get("steps", [])
                                            step_count = len(steps)
                                            print(f"[OK] Context Loaded: '{workflow_name}' with {step_count} steps.")
                                            
                                            # Debug: Show what's in the steps
                                            print(f"[WORKFLOW] WORKFLOW STEPS DETAIL:")
                                            for i, s in enumerate(steps[:5], 1):  # Show first 5
                                                s_action = s.get("action_type") if isinstance(s, dict) else s.action_type
                                                s_args = s.get("args") if isinstance(s, dict) else s.args
                                                print(f"   Step {i}: {s_action} | args={s_args}")
                                            
                                            await send_json({
                                                "type": "status", 
                                                "status": "planning",
                                                "message": f"loading knowledge from: {workflow_name}",
                                                "task_id": task_id
                                            })
                                else:
                                    print(f"[WARNING] No workflow match found for: {goal}")
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
                                print(f"\n[RUN] EXECUTING {len(subtasks_to_execute)} SUBTASKS SEQUENTIALLY")
                                
                                total_steps = 0
                                all_workflows = []
                                
                                for i, subtask in enumerate(subtasks_to_execute, 1):
                                    print(f"\n{'='*50}")
                                    print(f"[SUBTASK] SUBTASK {i}/{len(subtasks_to_execute)}: {subtask.action}")
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
                                        "message": f"Subtask {i}/{len(subtasks_to_execute)}: {subtask.action} {subtask.target}",
                                        "task_id": task_id
                                    })
                                    
                                    # Build subtask goal
                                    subtask_goal = f"{subtask.action} {subtask.target}"
                                    
                                    # ==============================================
                                    # CHECK IF THIS SUBTASK IS A HAMMER DOWNLOAD
                                    # ==============================================
                                    if is_hammer_download_intent(subtask_goal):
                                        print(f"\n[HAMMER] SUBTASK IS HAMMER DOWNLOAD - USING DIRECT API!")
                                        company = extract_company_from_goal(subtask_goal)
                                        
                                        if company:
                                            try:
                                                # Extract cookies from browser session
                                                auth_cookie = None
                                                if persistent_browser and persistent_browser.is_started:
                                                    auth_cookie = await persistent_browser.get_auth_cookies_header()
                                                    if auth_cookie:
                                                        print(f"[AUTH] Using browser session cookies for API auth")
                                                
                                                # Fetch company registry from static_data namespace
                                                companies_list = []
                                                try:
                                                    static_records = pinecone_service.find_all_static_data(limit=10)
                                                    for record in static_records:
                                                        data = record.get("data", "")
                                                        if data:
                                                            try:
                                                                parsed = json.loads(data) if isinstance(data, str) else data
                                                                if isinstance(parsed, list):
                                                                    companies_list.extend(parsed)
                                                            except json.JSONDecodeError:
                                                                pass
                                                    
                                                    if companies_list:
                                                        print(f"[HAMMER] Loaded {len(companies_list)} companies from static_data")
                                                    else:
                                                        print("[HAMMER] WARNING: No companies found in static_data namespace")
                                                except Exception as e:
                                                    print(f"[ERROR] Failed to load company registry from static_data: {e}")

                                                # Create downloader with browser cookies AND companies
                                                downloader = get_hammer_downloader(auth_cookie=auth_cookie, companies=companies_list)
                                                result = await downloader.download_and_index(company)
                                                
                                                if result.get("success"):
                                                    await send_json({
                                                        "type": "status",
                                                        "status": "completed", 
                                                        "message": f"Hammer indexed: {result.get('records_count', 0)} records from {result.get('company_name')}",
                                                        "task_id": task_id
                                                    })
                                                    
                                                    # Update session context
                                                    session_context.important_notes["hammer_company"] = result.get("company_name")
                                                    session_context.important_notes["hammer_records"] = str(result.get("records_count", 0))
                                                    
                                                    total_steps += 1
                                                    continue  # Skip to next subtask
                                                else:
                                                    print(f"[ERROR] Hammer download failed: {result.get('error')}")
                                                    # Don't continue - let agent try as fallback
                                            except Exception as e:
                                                print(f"[ERROR] Hammer download exception: {e}")
                                                # Don't continue - let agent try as fallback
                                    
                                    # Run agent for this subtask (normal browser automation)
                                    workflow = await agent.run(
                                        subtask_goal, 
                                        effective_start_url if i == 1 else "",  # Only use start_url for first subtask
                                        previous_workflow=subtask_workflow
                                    )
                                    
                                    total_steps += len(workflow.steps)
                                    all_workflows.append(workflow)
                                    
                                    print(f"   [OK] Subtask {i} completed with {len(workflow.steps)} steps")
                                
                                print(f"\n[COMPLETE] ALL {len(subtasks_to_execute)} SUBTASKS COMPLETED! Total steps: {total_steps}")
                                
                                await send_json({
                                    "type": "completed",
                                    "workflow_id": all_workflows[-1].id if all_workflows else task_id,
                                    "step_count": total_steps,
                                    "subtasks_completed": len(subtasks_to_execute),
                                    "task_id": task_id
                                })
                            else:
                                # ==============================================
                                # SINGLE TASK EXECUTION (original behavior)
                                # ==============================================
                                workflow = await agent.run(goal, effective_start_url, previous_workflow=recommended_workflow)
                                session_metrics.record_task_completed()
                                await send_json({
                                    "type": "completed",
                                    "workflow_id": workflow.id,
                                    "step_count": len(workflow.steps),
                                    "task_id": task_id
                                })
                        except asyncio.CancelledError:
                            session_metrics.record_task_failed()
                            await send_json({
                                "type": "status",
                                "status": "stopped",
                                "message": "Task cancelled",
                                "task_id": task_id
                            })
                        except Exception as e:
                            session_metrics.record_task_failed()
                            import traceback
                            traceback.print_exc()
                            await send_json({
                                "type": "error",
                                "message": str(e),
                                "task_id": task_id
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
                    print(f"\n[END] SESSION ENDING: {session_context.session_id}")
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
                    print(f"[SESSION] NEW SESSION CREATED: {session_context.session_id}")

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
                    
                    print(f"\n[INDEX] INDEXING HAMMER: {os.path.basename(file_path)}")
                    
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

                elif msg_type == "execute_test_plan":
                    # ==============================================
                    # DIRECT TEST PLAN EXECUTION (Alternative method)
                    # ==============================================
                    test_plan = message.get("test_plan")
                    options = message.get("options", {})

                    if not test_plan:
                        await send_json({"type": "error", "message": "test_plan is required"})
                        continue

                    print(f"[TEST PLAN] Direct execution: {test_plan.get('test_case_id', 'Unknown')}")

                    await send_json({
                        "type": "status",
                        "status": "running",
                        "message": f"Executing: {test_plan.get('test_case_id', 'Test Plan')}"
                    })

                    task_id = str(uuid.uuid4())

                    # Create browser if needed
                    if persistent_browser is None:
                        persistent_browser = BrowserController()
                        auth_service = get_auth_service()
                        storage_state = auth_service.get_storage_state()
                        await persistent_browser.start(storage_state=storage_state)

                    # Create Semantic QA Agent
                    semantic_agent = SemanticQAAgent(
                        browser=persistent_browser,
                        session_metrics=session_metrics
                    )

                    async def run_direct_test_plan():
                        try:
                            result = await semantic_agent.execute_test_plan(
                                test_plan,
                                stop_on_failure=options.get("stop_on_failure", True),
                                max_retries_per_step=options.get("max_retries", 3)
                            )

                            for step_result in result.steps_results:
                                status_emoji = "✓" if step_result.status == "pass" else "✗" if step_result.status == "fail" else "○"
                                await send_json({
                                    "type": "message",
                                    "role": "agent",
                                    "content": f"{status_emoji} Step {step_result.step_id} ({step_result.action}): {step_result.status.upper()}"
                                })

                            summary = f"### Test Complete: {result.overall_status.upper()}\n"
                            summary += f"Passed: {result.passed_steps} | Failed: {result.failed_steps} | Skipped: {result.skipped_steps}"

                            await send_json({
                                "type": "status",
                                "status": "completed",
                                "message": summary
                            })

                            await send_json({
                                "type": "completed",
                                "workflow_id": task_id,
                                "test_result": result.model_dump()
                            })

                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            await send_json({
                                "type": "error",
                                "message": f"Test execution failed: {str(e)}"
                            })

                    agent_task = asyncio.create_task(run_direct_test_plan())

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


# ==================== SEMANTIC QA EXECUTION ENDPOINTS ====================
# These endpoints support the new vision-based, semantic QA execution system.


class TestPlanValidateRequest(BaseModel):
    """Request model for test plan validation."""
    test_plan: dict


class TestPlanExecuteRequest(BaseModel):
    """Request model for test plan execution."""
    test_plan: dict
    start_from_step: int = 1
    stop_on_failure: bool = True
    max_retries_per_step: int = 3


class SingleStepExecuteRequest(BaseModel):
    """Request model for single step execution."""
    step: dict
    task_id: Optional[str] = None
    max_retries: int = 3


@app.post("/test-plans/validate")
async def validate_test_plan_endpoint(request: TestPlanValidateRequest):
    """
    Validate a test plan without executing it.

    This endpoint parses and validates the test plan structure,
    checking for:
    - Required fields (test_case_id, description, steps)
    - Valid action types
    - Required expected_visual for each step
    - No forbidden fields (coordinates, selectors)

    Returns validation result with parsed plan details or errors.
    """
    try:
        result = await validate_test_plan(request.test_plan)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/test-plans/sample")
async def get_sample_test_plan():
    """
    Get a sample test plan for reference.

    Returns a complete example test plan that demonstrates
    the correct format for semantic QA execution.
    """
    parser = TestPlanParser()
    return {
        "sample": parser.create_sample_test_plan(),
        "supported_actions": [action.value for action in SemanticActionType],
        "notes": {
            "expected_visual": "REQUIRED for every step - describes what should be visible after the action",
            "target_description": "Visual description of the element to interact with (for input, click, select)",
            "target": "URL for navigate actions",
            "value": "Text to enter for input/select actions",
            "forbidden_fields": ["x", "y", "coordinates", "selector", "css_selector", "xpath"]
        }
    }


@app.post("/test-plans/execute")
async def execute_test_plan_endpoint(
    request: TestPlanExecuteRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Execute a semantic test plan.

    This endpoint executes a complete test plan using:
    - Visual element location (Gemini Vision)
    - Semantic action execution
    - Visual verification after each step
    - Evidence collection

    For real-time updates during execution, use the WebSocket endpoint
    /ws/test-plan instead.

    Returns complete execution results with pass/fail status for each step.
    """
    try:
        # Create browser and agent
        browser = BrowserController()
        agent = create_semantic_qa_agent(browser=browser)

        try:
            # Execute the test plan
            result = await agent.execute_test_plan(
                request.test_plan,
                start_from_step=request.start_from_step,
                stop_on_failure=request.stop_on_failure,
                max_retries_per_step=request.max_retries_per_step
            )

            return result.model_dump()

        finally:
            await agent.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test-plans/step")
async def execute_single_step_endpoint(
    request: SingleStepExecuteRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Execute a single test step.

    Useful for:
    - Running individual steps
    - Re-running failed steps
    - Step-by-step debugging

    The browser session is created fresh for each call.
    For persistent sessions, use the WebSocket endpoint.
    """
    try:
        browser = BrowserController()
        agent = create_semantic_qa_agent(browser=browser)

        try:
            result = await agent.execute_single_step(
                request.step,
                task_id=request.task_id,
                max_retries=request.max_retries
            )

            return result.model_dump()

        finally:
            await agent.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/test-plan")
async def websocket_test_plan_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time semantic QA test execution.

    This endpoint provides real-time updates during test plan execution,
    including:
    - Step status changes (pending, running, pass, fail)
    - Screenshots after each step
    - Overall progress
    - Evidence on failure

    Client sends:
        {"type": "execute", "test_plan": {...}, "options": {...}}
        {"type": "execute_step", "step": {...}, "step_id": 1}
        {"type": "resume", "test_plan": {...}, "from_step": 3}
        {"type": "stop"}

    Server sends:
        {"type": "status", "test_case_id": "...", "current_step": 1, "status": "running"}
        {"type": "step_result", "step_id": 1, "status": "pass", "evidence": {...}}
        {"type": "screenshot", "data": "base64..."}
        {"type": "completed", "result": {...}}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()
    WEBSOCKET_CONNECTIONS.inc()

    # Session state
    browser: Optional[BrowserController] = None
    agent: Optional[SemanticQAAgent] = None
    execution_task: Optional[asyncio.Task] = None
    session_metrics = SessionMetrics(session_id=str(uuid.uuid4()))

    async def send_json(data: dict):
        """Helper to send JSON message."""
        try:
            await websocket.send_text(json.dumps(data))
            session_metrics.record_message_sent()
        except Exception as e:
            logger.warning("websocket_send_error", error=str(e))

    async def on_step_status(step_id: int, status: StepStatus, message: str):
        """Callback for step status updates."""
        await send_json({
            "type": "step_status",
            "step_id": step_id,
            "status": status.value if hasattr(status, 'value') else status,
            "message": message
        })

    async def on_execution_status(status: TestPlanExecutionStatus):
        """Callback for overall execution status."""
        await send_json({
            "type": "execution_status",
            "test_case_id": status.test_case_id,
            "current_step_id": status.current_step_id,
            "current_step_status": status.current_step_status.value if hasattr(status.current_step_status, 'value') else status.current_step_status,
            "progress": status.overall_progress,
            "steps_status": {k: (v.value if hasattr(v, 'value') else v) for k, v in status.steps_status.items()},
            "message": status.message
        })

    async def on_screenshot(step_id: int, screenshot_b64: str):
        """Callback to send screenshots with step_id."""
        await send_json({
            "type": "screenshot",
            "step_id": step_id,
            "data": screenshot_b64
        })

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                message = json.loads(data)
                msg_type = message.get("type")
                session_metrics.record_message_received()

                if msg_type == "execute":
                    # Execute a complete test plan
                    test_plan = message.get("test_plan")
                    options = message.get("options", {})

                    if not test_plan:
                        await send_json({"type": "error", "message": "test_plan is required"})
                        continue

                    # Cancel any running execution
                    if execution_task and not execution_task.done():
                        execution_task.cancel()
                        try:
                            await execution_task
                        except asyncio.CancelledError:
                            pass

                    # Create browser if needed
                    if browser is None:
                        browser = BrowserController()

                    # Create agent with callbacks
                    agent = SemanticQAAgent(
                        browser=browser,
                        on_step_status=on_step_status,
                        on_execution_status=on_execution_status,
                        on_screenshot=on_screenshot,
                        session_metrics=session_metrics
                    )

                    async def run_execution():
                        try:
                            result = await agent.execute_test_plan(
                                test_plan,
                                start_from_step=options.get("start_from_step", 1),
                                stop_on_failure=options.get("stop_on_failure", True),
                                max_retries_per_step=options.get("max_retries_per_step", 3)
                            )

                            await send_json({
                                "type": "completed",
                                "result": result.model_dump()
                            })

                        except asyncio.CancelledError:
                            await send_json({
                                "type": "status",
                                "status": "stopped",
                                "message": "Execution cancelled"
                            })
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            await send_json({
                                "type": "error",
                                "message": str(e)
                            })

                    execution_task = asyncio.create_task(run_execution())

                elif msg_type == "execute_step":
                    # Execute a single step
                    step = message.get("step")

                    if not step:
                        await send_json({"type": "error", "message": "step is required"})
                        continue

                    # Create browser if needed
                    if browser is None:
                        browser = BrowserController()
                        await browser.start()

                    # Create agent if needed
                    if agent is None:
                        agent = SemanticQAAgent(
                            browser=browser,
                            on_step_status=on_step_status,
                            on_screenshot=on_screenshot,
                            session_metrics=session_metrics
                        )

                    try:
                        result = await agent.execute_single_step(
                            step,
                            task_id=message.get("task_id"),
                            max_retries=message.get("max_retries", 3)
                        )

                        await send_json({
                            "type": "step_result",
                            "step_id": result.step_id,
                            "status": result.status.value if hasattr(result.status, 'value') else result.status,
                            "result": result.model_dump()
                        })

                    except Exception as e:
                        await send_json({
                            "type": "error",
                            "message": str(e)
                        })

                elif msg_type == "resume":
                    # Resume execution from a specific step
                    test_plan = message.get("test_plan")
                    from_step = message.get("from_step", 1)

                    if not test_plan:
                        await send_json({"type": "error", "message": "test_plan is required"})
                        continue

                    if agent is None:
                        if browser is None:
                            browser = BrowserController()
                        agent = SemanticQAAgent(
                            browser=browser,
                            on_step_status=on_step_status,
                            on_execution_status=on_execution_status,
                            on_screenshot=on_screenshot,
                            session_metrics=session_metrics
                        )

                    async def run_resume():
                        try:
                            result = await agent.resume_from_step(
                                test_plan,
                                step_id=from_step
                            )

                            await send_json({
                                "type": "completed",
                                "result": result.model_dump()
                            })

                        except Exception as e:
                            await send_json({
                                "type": "error",
                                "message": str(e)
                            })

                    execution_task = asyncio.create_task(run_resume())

                elif msg_type == "stop":
                    # Stop execution
                    if agent:
                        agent.stop()
                    if execution_task and not execution_task.done():
                        execution_task.cancel()

                    await send_json({
                        "type": "status",
                        "status": "stopping",
                        "message": "Stop requested"
                    })

                elif msg_type == "close_browser":
                    # Close browser
                    if browser:
                        await browser.stop()
                        browser = None
                        agent = None

                    await send_json({
                        "type": "status",
                        "status": "idle",
                        "message": "Browser closed"
                    })

                elif msg_type == "get_screenshot":
                    # Get current screenshot
                    if browser and browser.is_started:
                        screenshot = await browser.get_screenshot_base64()
                        await send_json({
                            "type": "screenshot",
                            "data": screenshot
                        })
                    else:
                        await send_json({
                            "type": "error",
                            "message": "Browser not started"
                        })

                elif msg_type == "ping":
                    await send_json({"type": "pong"})

            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        logger.info("test_plan_websocket_disconnected")
        if agent:
            agent.stop()
        if execution_task and not execution_task.done():
            execution_task.cancel()
        if browser:
            await browser.stop()
    except Exception as e:
        logger.error("test_plan_websocket_error", error=str(e))
        if browser:
            await browser.stop()
    finally:
        WEBSOCKET_CONNECTIONS.dec()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
