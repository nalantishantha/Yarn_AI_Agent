from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.agent.graph import agent_graph
from langchain_core.messages import HumanMessage, ToolMessage
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

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")
        
    config = {"configurable": {"thread_id": req.thread_id}}
    
    # If the user is responding to an interrupt (like approving a policy), 
    # we just pass their message back into the graph.
    messages = [HumanMessage(content=req.message)] if req.message else None
    
    try:
        response = agent_graph.invoke({"messages": messages} if messages else None, config)
        
        # Check if the graph was interrupted (e.g. for a sensitive tool call)
        state = agent_graph.get_state(config)
        
        if state.next and "sensitive_tools" in state.next:
            # We hit an interrupt! We need to ask the user for confirmation.
            last_msg = state.values["messages"][-1]
            proposed_policy = None
            if hasattr(last_msg, "tool_calls"):
                for call in last_msg.tool_calls:
                    if call["name"] == "add_sourcing_constraint_tool":
                        proposed_policy = call["args"]
                        
            return ChatResponse(
                reply="I need your permission to write this policy to the database. Do you approve? (Yes/No)",
                is_interrupted=True,
                pending_tool_call=proposed_policy
            )
            
        # Normal execution finished
        if response and "messages" in response:
            final_msg = response["messages"][-1]
            reply_text = final_msg.content
            if isinstance(reply_text, list):
                reply_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in reply_text])
            return ChatResponse(reply=str(reply_text))
            
        return ChatResponse(reply="No response from agent.")
        
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
        # Simulate the tool returning the rejection message
        agent_graph.update_state(config, {"messages": [rejection_msg]}, as_node="sensitive_tools")
        
        # Resume the graph
        response = agent_graph.invoke(None, config)
        if response and "messages" in response:
            final_msg = response["messages"][-1]
            reply_text = final_msg.content
            if isinstance(reply_text, list):
                reply_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in reply_text])
            return ChatResponse(reply=str(reply_text))
            
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
        # Resume the graph with None. The ToolNode will execute the tool automatically.
        response = agent_graph.invoke(None, config)
        if response and "messages" in response:
            final_msg = response["messages"][-1]
            reply_text = final_msg.content
            if isinstance(reply_text, list):
                reply_text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in reply_text])
            return ChatResponse(reply=str(reply_text))
            
        return ChatResponse(reply="No response from agent.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
