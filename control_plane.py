#!/usr/bin/env python3
"""DHARMA SWARM CONTROL PLANE — Stable wrapper for phone control.

Usage:
    python3 control_plane.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# =============================================================================
# SAFE IMPORTS — handle missing dependencies gracefully
# =============================================================================

_import_errors = []

# FastAPI imports
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
except ImportError as e:
    _import_errors.append(f"FastAPI/Pydantic: {e}")
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None

# dharma_swarm imports — wrapped in try/except
try:
    REPO_ROOT = Path(__file__).parent
    sys.path.insert(0, str(REPO_ROOT))
    from dharma_swarm.models import AgentRole, TaskPriority
    from dharma_swarm.swarm import SwarmManager
    _DHARMA_AVAILABLE = True
except ImportError as e:
    _DHARMA_AVAILABLE = False
    _import_errors.append(f"dharma_swarm: {e}")
    AgentRole = None
    TaskPriority = None
    SwarmManager = None

# =============================================================================
# AGENT REGISTRY
# =============================================================================

@dataclass
class AgentDef:
    name: str
    role: str
    model: str
    provider: str = "openrouter"
    description: str = ""

AGENT_REGISTRY: dict[str, AgentDef] = {
    "glm_builder": AgentDef(
        name="glm_builder",
        role="coder",
        model="anthropic/claude-sonnet-4",
        description="Technical/code agent",
    ),
    "minimax_fast": AgentDef(
        name="minimax_fast",
        role="worker",
        model="google/gemini-flash-1.5",
        description="Fast/simple agent",
    ),
    "kimi_operator": AgentDef(
        name="kimi_operator",
        role="researcher",
        model="kimi/k2",
        description="Market/external agent",
    ),
    "code": AgentDef(name="glm_builder", role="coder", model="anthropic/claude-sonnet-4", description="Alias"),
    "fast": AgentDef(name="minimax_fast", role="worker", model="google/gemini-flash-1.5", description="Alias"),
    "market": AgentDef(name="kimi_operator", role="researcher", model="kimi/k2", description="Alias"),
}

# =============================================================================
# ROUTER
# =============================================================================

def route_agent(task_description: str) -> str:
    """Route task to appropriate agent."""
    task_lower = task_description.lower()
    
    technical_keywords = ["code", "implement", "build", "fix", "debug", "refactor", "python", "bug", "error"]
    fast_keywords = ["quick", "fast", "simple", "small", "check", "verify", "status"]
    market_keywords = ["market", "research", "competitor", "pricing", "search", "analyze", "opportunity"]
    
    tech_score = sum(1 for kw in technical_keywords if kw in task_lower)
    fast_score = sum(1 for kw in fast_keywords if kw in task_lower)
    market_score = sum(1 for kw in market_keywords if kw in task_lower)
    
    if fast_score >= max(tech_score, market_score) and fast_score > 0:
        return "minimax_fast"
    elif market_score >= tech_score and market_score > 0:
        return "kimi_operator"
    return "glm_builder"

# =============================================================================
# STANDARDIZE OUTPUT
# =============================================================================

def standardize_response(
    status: str,
    agent: str,
    task: str,
    result: Any = None,
    steps: list[str] | None = None,
    error: str | None = None,
) -> dict:
    """Standardize all outputs."""
    return {
        "status": status,
        "agent": agent,
        "task": task,
        "result": result if result is not None else {},
        "steps": steps if steps is not None else [],
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# =============================================================================
# MOCK RESPONSES — used when dharma_swarm is unavailable
# =============================================================================

def _mock_spawn_agent(agent_def: AgentDef, task: str) -> dict:
    """Return mock agent response when real spawn is unavailable."""
    return {
        "agent_id": f"mock-{agent_def.name}-{datetime.now().strftime('%H%M%S')}",
        "agent_name": agent_def.name,
        "task_id": f"task-{datetime.now().strftime('%H%M%S')}",
        "task_status": "accepted",
        "message": f"[MOCK] Agent {agent_def.name} would process: {task[:60]}...",
        "note": "Running in mock mode - dharma_swarm not available or misconfigured",
    }

# =============================================================================
# SAFE EXECUTION WRAPPERS
# =============================================================================

async def _safe_get_swarm() -> tuple[Any, list[str]]:
    """Safely initialize swarm. Returns (swarm_or_none, steps)."""
    steps = []
    
    if not _DHARMA_AVAILABLE:
        steps.append("dharma_swarm not available (import failed)")
        return None, steps
    
    try:
        state_dir = Path.home() / ".dharma"
        state_dir.mkdir(parents=True, exist_ok=True)
        steps.append(f"State dir: {state_dir}")
        
        swarm = SwarmManager(state_dir=str(state_dir))
        steps.append("SwarmManager created")
        
        await swarm.init()
        steps.append("Swarm initialized")
        
        return swarm, steps
    except Exception as e:
        steps.append(f"Swarm init failed: {str(e)}")
        return None, steps

async def _run_single_agent(agent_id: str, task: str, context: dict) -> dict:
    """Execute single agent with comprehensive error handling."""
    steps = []
    
    # Step 1: Resolve agent
    try:
        agent_def = AGENT_REGISTRY.get(agent_id)
        if not agent_def:
            return standardize_response(
                status="error",
                agent=agent_id,
                task=task,
                error=f"Unknown agent: {agent_id}",
                steps=["Failed to resolve agent"],
            )
        steps.append(f"Resolved agent: {agent_def.name}")
    except Exception as e:
        return standardize_response(
            status="error",
            agent=agent_id,
            task=task,
            error=f"Registry error: {str(e)}",
            steps=["Failed to access agent registry"],
        )
    
    # Step 2: Check dharma_swarm availability
    if not _DHARMA_AVAILABLE:
        steps.append("dharma_swarm unavailable - using mock mode")
        return standardize_response(
            status="success",
            agent=agent_def.name,
            task=task,
            result=_mock_spawn_agent(agent_def, task),
            steps=steps,
        )
    
    # Step 3: Initialize swarm
    swarm, swarm_steps = await _safe_get_swarm()
    steps.extend(swarm_steps)
    
    if swarm is None:
        steps.append("Falling back to mock mode")
        return standardize_response(
            status="success",
            agent=agent_def.name,
            task=task,
            result=_mock_spawn_agent(agent_def, task),
            steps=steps,
        )
    
    # Step 4: Spawn agent
    try:
        agent_state = await swarm.spawn_agent(
            name=agent_def.name,
            role=AgentRole(agent_def.role),
            model=agent_def.model,
        )
        steps.append(f"Spawned: {agent_state.name} ({agent_state.id[:8]}...)")
    except Exception as e:
        steps.append(f"Spawn failed: {str(e)}")
        return standardize_response(
            status="success",  # Return success with mock
            agent=agent_def.name,
            task=task,
            result=_mock_spawn_agent(agent_def, task),
            steps=steps,
        )
    
    # Step 5: Create task
    try:
        task_obj = await swarm.create_task(
            title=task[:100],
            description=task,
            priority=TaskPriority.HIGH,
            metadata={"requested_agent": agent_state.id, "agent_name": agent_def.name},
        )
        steps.append(f"Created task: {task_obj.id[:8]}...")
    except Exception as e:
        steps.append(f"Task creation failed: {str(e)}")
        return standardize_response(
            status="success",
            agent=agent_def.name,
            task=task,
            result={
                "agent_id": agent_state.id,
                "agent_name": agent_state.name,
                "task_id": None,
                "task_status": "agent_only",
                "message": f"Agent spawned but task creation failed",
            },
            steps=steps,
        )
    
    # Step 6: Dispatch
    try:
        await swarm.dispatch_next()
        steps.append("Dispatched")
    except Exception as e:
        steps.append(f"Dispatch warning: {str(e)}")
    
    # Build success response
    result = {
        "agent_id": agent_state.id,
        "agent_name": agent_state.name,
        "task_id": task_obj.id,
        "task_status": task_obj.status.value if hasattr(task_obj.status, 'value') else str(task_obj.status),
        "message": f"Agent {agent_def.name} processing: {task[:60]}...",
    }
    
    return standardize_response(
        status="success",
        agent=agent_def.name,
        task=task,
        result=result,
        steps=steps,
    )

async def _run_swarm(task: str, agents: list[str] | None, parallel: bool) -> dict:
    """Execute multi-agent with error handling."""
    steps = []
    
    # Auto-select agents
    if not agents:
        primary = route_agent(task)
        agents = [primary, "minimax_fast"]
        steps.append(f"Auto-selected: {agents}")
    else:
        steps.append(f"User-specified: {agents}")
    
    # Execute
    results = []
    errors = []
    
    if parallel:
        tasks_coro = [_run_single_agent(agent, task, {}) for agent in agents]
        agent_results = await asyncio.gather(*tasks_coro, return_exceptions=True)
        
        for agent, result in zip(agents, agent_results):
            if isinstance(result, Exception):
                errors.append(f"{agent}: {str(result)}")
                results.append(standardize_response(
                    status="error",
                    agent=agent,
                    task=task,
                    error=str(result),
                    steps=["Exception during execution"],
                ))
            else:
                results.append(result)
    else:
        for agent in agents:
            try:
                result = await _run_single_agent(agent, task, {})
                results.append(result)
            except Exception as e:
                errors.append(f"{agent}: {str(e)}")
                results.append(standardize_response(
                    status="error",
                    agent=agent,
                    task=task,
                    error=str(e),
                    steps=["Exception during execution"],
                ))
    
    return standardize_response(
        status="success" if not errors else "partial_error",
        agent="swarm",
        task=task,
        result={
            "agents_used": agents,
            "parallel": parallel,
            "agent_results": results,
            "errors": errors if errors else None,
        },
        steps=steps,
    )

# =============================================================================
# FASTAPI APP (if available)
# =============================================================================

if FastAPI is None:
    # Fallback: create minimal app that returns errors
    logger.error("=" * 60)
    logger.error("CRITICAL: FastAPI not available")
    for err in _import_errors:
        logger.error(f"  - {err}")
    logger.error("=" * 60)
    logger.error("Install: pip install fastapi uvicorn pydantic")
    
    # Dummy app that just logs error
    class DummyApp:
        pass
    app = DummyApp()
else:
    app = FastAPI(
        title="DHARMA CONTROL PLANE",
        description="Stable control layer for dharma_swarm",
        version="0.1.0",
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch ALL unhandled exceptions."""
        logger.error(f"Unhandled exception: {exc}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content=standardize_response(
                status="error",
                agent="system",
                task="unknown",
                error=f"Internal error: {str(exc)}",
                steps=["Unhandled exception caught by global handler"],
            ),
        )
    
    @app.get("/")
    async def root():
        """Web UI."""
        return HTMLResponse(content=HTML_UI)
    
    @app.get("/health")
    async def health():
        """Health check."""
        keys = {
            "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY")),
            "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY")),
            "KIMI_API_KEY": bool(os.environ.get("KIMI_API_KEY")),
        }
        
        return standardize_response(
            status="success",
            agent="system",
            task="health_check",
            result={
                "dharma_swarm_available": _DHARMA_AVAILABLE,
                "import_errors": _import_errors if _import_errors else None,
                "api_keys": keys,
                "agents": list(AGENT_REGISTRY.keys()),
            },
            steps=["Health check completed"],
        )
    
    @app.get("/status")
    async def status():
        """System status."""
        if not _DHARMA_AVAILABLE:
            return standardize_response(
                status="success",
                agent="system",
                task="status_check",
                result={"note": "dharma_swarm unavailable", "mock_mode": True},
                steps=["Running in mock mode"],
            )
        
        swarm, steps = await _safe_get_swarm()
        if swarm is None:
            return standardize_response(
                status="success",
                agent="system",
                task="status_check",
                result={"note": "Swarm unavailable", "mock_mode": True},
                steps=steps,
            )
        
        try:
            swarm_status = await swarm.status()
            await swarm.shutdown()
            return standardize_response(
                status="success",
                agent="system",
                task="status_check",
                result={
                    "agents": len(swarm_status.agents) if hasattr(swarm_status, 'agents') else 0,
                    "mock_mode": False,
                },
                steps=steps + ["Status retrieved"],
            )
        except Exception as e:
            return standardize_response(
                status="success",
                agent="system",
                task="status_check",
                result={"note": str(e), "mock_mode": True},
                steps=steps + [f"Error: {str(e)}"],
            )
    
    @app.post("/run-agent")
    async def run_agent(request: dict):
        """Run single agent."""
        try:
            task = request.get("task", "")
            agent_id = request.get("agent")
            context = request.get("context", {})
            
            if not task:
                return standardize_response(
                    status="error",
                    agent="none",
                    task="",
                    error="Missing 'task' field",
                    steps=["Validation failed"],
                )
            
            if not agent_id:
                agent_id = route_agent(task)
            
            result = await _run_single_agent(agent_id, task, context)
            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"run_agent error: {e}")
            return JSONResponse(
                content=standardize_response(
                    status="error",
                    agent="system",
                    task=request.get("task", "unknown"),
                    error=str(e),
                    steps=["Exception in run_agent endpoint"],
                )
            )
    
    @app.post("/run-swarm")
    async def run_swarm(request: dict):
        """Run multi-agent."""
        try:
            task = request.get("task", "")
            agents = request.get("agents")
            parallel = request.get("parallel", True)
            
            if not task:
                return standardize_response(
                    status="error",
                    agent="none",
                    task="",
                    error="Missing 'task' field",
                    steps=["Validation failed"],
                )
            
            result = await _run_swarm(task, agents, parallel)
            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"run_swarm error: {e}")
            return JSONResponse(
                content=standardize_response(
                    status="error",
                    agent="swarm",
                    task=request.get("task", "unknown"),
                    error=str(e),
                    steps=["Exception in run_swarm endpoint"],
                )
            )
    
    @app.get("/agents")
    async def list_agents():
        """List agents."""
        try:
            return standardize_response(
                status="success",
                agent="system",
                task="list_agents",
                result={
                    "agents": {
                        name: {"role": d.role, "model": d.model, "desc": d.description}
                        for name, d in AGENT_REGISTRY.items()
                    }
                },
                steps=["Registry accessed"],
            )
        except Exception as e:
            return standardize_response(
                status="error",
                agent="system",
                task="list_agents",
                error=str(e),
                steps=["Failed to read registry"],
            )

# =============================================================================
# WEB UI
# =============================================================================

HTML_UI = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DHARMA CONTROL</title>
<style>
body{font-family:system-ui,sans-serif;max-width:600px;margin:40px auto;padding:20px}
h1{font-size:24px;margin-bottom:10px}.subtitle{color:#666;margin-bottom:30px}
textarea{width:100%;height:100px;padding:10px;font-size:16px;border:1px solid #ccc;border-radius:4px}
button{background:#0066cc;color:white;padding:12px 24px;font-size:16px;border:none;border-radius:4px;cursor:pointer;margin-top:10px;margin-right:10px}
button:hover{background:#0055aa}button:disabled{background:#ccc;cursor:not-allowed}
#output{margin-top:20px;padding:15px;background:#f5f5f5;border-radius:4px;white-space:pre-wrap;font-family:monospace;font-size:14px;min-height:100px}
.status-success{color:green}.status-error{color:red}.status-partial_error{color:orange}
.agent-tag{display:inline-block;background:#e0e0e0;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:5px}
</style></head>
<body>
<h1>DHARMA CONTROL</h1><div class="subtitle">Send commands to your swarm</div>
<textarea id="command" placeholder="Enter command..."></textarea><br>
<button id="runBtn" onclick="runCommand()">RUN AGENT</button>
<button id="swarmBtn" onclick="runSwarm()" style="background:#555">RUN SWARM</button>
<div id="output">Output will appear here...</div>
<script>
async function runCommand(){const cmd=document.getElementById('command').value;if(!cmd){alert('Enter command');return}const btn=document.getElementById('runBtn'),output=document.getElementById('output');btn.disabled=true;output.textContent='Running...';try{const res=await fetch('/run-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:cmd})});const data=await res.json();displayResult(data)}catch(e){output.innerHTML='<span class="status-error">Error: '+e.message+'</span>'}btn.disabled=false}
async function runSwarm(){const cmd=document.getElementById('command').value;if(!cmd){alert('Enter command');return}const btn=document.getElementById('swarmBtn'),output=document.getElementById('output');btn.disabled=true;output.textContent='Running swarm...';try{const res=await fetch('/run-swarm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:cmd})});const data=await res.json();displayResult(data)}catch(e){output.innerHTML='<span class="status-error">Error: '+e.message+'</span>'}btn.disabled=false}
function displayResult(data){const output=document.getElementById('output');let html='';html+='<div><strong>Status:</strong> <span class="status-'+data.status+'">'+data.status.toUpperCase()+'</span></div>';html+='<div><strong>Agent:</strong> <span class="agent-tag">'+data.agent+'</span></div>';html+='<div><strong>Task:</strong> '+(data.task||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</div>';if(data.steps&&data.steps.length){html+='<div><strong>Steps:</strong></div><ul>';data.steps.forEach(s=>{html+='<li>'+(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</li>'});html+='</ul>'}if(data.result){html+='<div><strong>Result:</strong></div><pre>'+JSON.stringify(data.result,null,2)+'</pre>'}if(data.error){html+='<div class="status-error"><strong>Error:</strong> '+(data.error||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</div>'}output.innerHTML=html}
</script></body></html>"""

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if FastAPI is None:
        print("=" * 60)
        print("ERROR: FastAPI is required")
        for err in _import_errors:
            print(f"  - {err}")
        print("=" * 60)
        print("Fix: pip install fastapi uvicorn pydantic")
        sys.exit(1)
    
    import uvicorn
    
    port = int(os.environ.get("CONTROL_PLANE_PORT", "8080"))
    host = os.environ.get("CONTROL_PLANE_HOST", "0.0.0.0")
    
    print("=" * 60)
    print("DHARMA CONTROL PLANE")
    print("=" * 60)
    print(f"URL: http://{host}:{port}/")
    print(f"Health: http://{host}:{port}/health")
    
    if _import_errors:
        print("-" * 60)
        print("IMPORT WARNINGS:")
        for err in _import_errors:
            print(f"  ⚠️  {err}")
    
    print("-" * 60)
    print(f"dharma_swarm: {'✅ Available' if _DHARMA_AVAILABLE else '❌ Unavailable (mock mode)'}")
    print("=" * 60)
    
    uvicorn.run(app, host=host, port=port)
