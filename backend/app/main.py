from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from app.agent.graph import agent_graph
from langchain_core.messages import HumanMessage, ToolMessage
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import crud
from app.schemas import schemas
import uuid

# --- ADDED FOR DEVELOPMENT LOGGING ---
import logging
from langchain_core.globals import set_debug
set_debug(True)
print("LangChain Debug Mode: ON. You will see detailed step-by-step logs in this terminal.")
# -------------------------------------

app = FastAPI(title="Yarn AI Agent API")

# Configure CORS for local development (React runs on 5173 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str

class ChatResponse(BaseModel):
    reply: str
    is_interrupted: bool = False
    pending_tool_call: dict = None

def extract_reply_text(state_before, state_after):
    start_idx = len(state_before.values.get("messages", [])) if state_before and state_before.values else 0
    all_messages = state_after.values.get("messages", []) if state_after and state_after.values else []
    new_msgs = all_messages[start_idx:]
    
    reply_parts = []
    for msg in new_msgs:
        if msg.type == "ai" and getattr(msg, "content", None):
            content = msg.content
            if isinstance(content, list):
                content = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
            if content.strip():
                reply_parts.append(content.strip())
    
    return "\n\n".join(reply_parts)

def build_chat_response(current_state, new_state) -> ChatResponse:
    reply_text = extract_reply_text(current_state, new_state)

    if new_state.next and "sensitive_tools" in new_state.next:
        all_messages = new_state.values.get("messages", [])
        last_msg = all_messages[-1] if all_messages else None
        proposed_policy = {}
        if last_msg and hasattr(last_msg, "tool_calls"):
            for call in last_msg.tool_calls:
                if call["name"] == "add_sourcing_constraint_tool":
                    proposed_policy = call["args"]

        narration = reply_text or (
            f"Regarding a proposed policy "
            f"({proposed_policy.get('constraint_type', 'policy')} on "
            f"{proposed_policy.get('target_value', 'target')}):"
        )
        return ChatResponse(
            reply=f"{narration}\n\nI need your permission to write this policy to the database. Do you approve? (Yes/No)",
            is_interrupted=True,
            pending_tool_call=proposed_policy,
        )

    if reply_text:
        return ChatResponse(reply=reply_text)
    return ChatResponse(reply="No response from agent.")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    if not req.thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")
        
    session = crud.touch_chat_session(db, req.thread_id)
    if not session:
        title = req.message[:30] + "..." if len(req.message) > 30 else req.message
        if not title: title = "New Chat"
        crud.create_chat_session(db, req.thread_id, title=title)
        
    config = {"configurable": {"thread_id": req.thread_id}}
    messages = [HumanMessage(content=req.message)] if req.message else None
    
    try:
        current_state = agent_graph.get_state(config)
        agent_graph.invoke({"messages": messages} if messages else None, config)
        new_state = agent_graph.get_state(config)
        
        return build_chat_response(current_state, new_state)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/reject-tool")
async def reject_tool_endpoint(req: ChatRequest):
    """
    Called when the user explicitly rejects a sensitive tool call (like writing a policy).
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    state = agent_graph.get_state(config)
    
    if not state.next or "sensitive_tools" not in state.next:
        raise HTTPException(status_code=400, detail="No pending sensitive tool call to reject.")
        
    last_msg = state.values["messages"][-1]
    tool_call_id = None
    if hasattr(last_msg, "tool_calls"):
        for call in last_msg.tool_calls:
            if call["name"] == "add_sourcing_constraint_tool":
                tool_call_id = call.get("id")
                
    if tool_call_id:
        rejection_msg = ToolMessage(
            content="Error: The user explicitly rejected saving this policy to the database. Acknowledge this and proceed with the rest of the query.",
            name="add_sourcing_constraint_tool",
            tool_call_id=tool_call_id
        )
        try:
            current_state = agent_graph.get_state(config)
            agent_graph.update_state(config, {"messages": [rejection_msg]}, as_node="sensitive_tools")
            
            agent_graph.invoke(None, config)
            new_state = agent_graph.get_state(config)
            
            return build_chat_response(current_state, new_state)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    return ChatResponse(reply="Failed to reject tool.")

@app.post("/api/chat/approve-tool")
async def approve_tool_endpoint(req: ChatRequest):
    """
    Called when the user explicitly approves a sensitive tool call.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    state = agent_graph.get_state(config)
    
    if not state.next or "sensitive_tools" not in state.next:
        raise HTTPException(status_code=400, detail="No pending sensitive tool call to approve.")
        
    try:
        current_state = agent_graph.get_state(config)
        agent_graph.invoke(None, config)
        new_state = agent_graph.get_state(config)
        
        return build_chat_response(current_state, new_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/sessions", response_model=List[schemas.ChatSessionResponse])
async def get_sessions(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return crud.get_chat_sessions(db, skip=skip, limit=limit)

@app.delete("/api/chat/sessions/{thread_id}")
async def delete_session(thread_id: str, db: Session = Depends(get_db)):
    success = crud.delete_chat_session(db, thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success"}

@app.get("/api/chat/sessions/{thread_id}/messages")
async def get_session_messages(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = agent_graph.get_state(config)
    messages = state.values.get("messages", [])
    
    formatted_messages = []
    
    for idx, msg in enumerate(messages):
        if msg.type == "human":
            formatted_messages.append({"text": msg.content, "isUser": True})
        elif msg.type == "ai" and msg.content:
            content = msg.content
            if isinstance(content, list):
                content = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
            if content.strip():
                is_interrupted = False
                pending_tool_call = None
                if idx == len(messages) - 1 and state.next and "sensitive_tools" in state.next:
                    is_interrupted = True
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for call in msg.tool_calls:
                            if call["name"] == "add_sourcing_constraint_tool":
                                pending_tool_call = call["args"]
                
                formatted_messages.append({
                    "text": content.strip(),
                    "isUser": False,
                    "isInterrupted": is_interrupted,
                    "pendingToolCall": pending_tool_call
                })
    
    return {"messages": formatted_messages}
