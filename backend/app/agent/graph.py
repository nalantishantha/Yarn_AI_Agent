import os
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from app.agent.state import AgentState
from app.agent.tools import AGENT_TOOLS

# Make sure env is loaded
load_dotenv()

# Initialize Gemini LLM (Primary)
gemini_llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
gemini_with_tools = gemini_llm.bind_tools(AGENT_TOOLS)

# Initialize OpenAI LLM (Fallback)
# Requires OPENAI_API_KEY in .env
openai_llm = ChatOpenAI(model="gpt-4o-mini")
openai_with_tools = openai_llm.bind_tools(AGENT_TOOLS)

# Combine with fallback: If Gemini hits a rate limit, LangChain automatically tries OpenAI!
llm_with_tools = gemini_with_tools.with_fallbacks([openai_with_tools])

from langchain_core.messages import SystemMessage

SYSTEM_PROMPT = """You are a Yarn Selection AI Agent.
When a user asks to find yarns, follow this EXACT 2-step process:

STEP 1: FILTERING
Call `filter_yarns_tool` with the exact attributes the user mentioned.
Wait for the database to return the matching yarns. Do NOT call `score_yarns_tool` in the same step.

STEP 2: SCORING / RANKING
If `filter_yarns_tool` returns multiple yarns, you MUST score and rank them using `score_yarns_tool`.
However, BEFORE calling `score_yarns_tool`, determine the priority weights:
- If the user explicitly provided exact numeric percentages (e.g. "70% price, 30% lead time"), use them immediately.
- If the user gave vague priorities or no priorities (and has not yet confirmed any percentages), YOU MUST STOP AND ASK FOR PERMISSION.
  1. Predict logical percentages based on their prompt.
  2. Present the predicted percentages to the user.
  3. Ask for their permission by offering exactly these 4 options:
     Option 1: Yes, use these percentages.
     Option 2: Give me more options.
     Option 3: Use equal percentages.
     Option 4: I will provide my own percentages.
  4. Wait for the user's reply. Do NOT call `score_yarns_tool` yet.

When the user gives permission (or you already have explicit percentages), call `score_yarns_tool`, passing the list of Material Numbers from Step 1, and the dictionary of decimal weights (0.0 to 1.0).
Present the final scored results to the user.
"""

def call_model(state: AgentState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": response}

def create_agent_graph():
    """
    Creates and compiles the LangGraph for the Yarn Agent.
    """
    builder = StateGraph(AgentState)
    
    # Add Nodes
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(AGENT_TOOLS))
    
    # Add Edges
    builder.add_edge(START, "agent")
    
    # Conditional edge: if LLM calls tool -> go to tools. Otherwise -> END.
    builder.add_conditional_edges(
        "agent",
        tools_condition,
    )
    
    builder.add_edge("tools", "agent")
    
    # Compile with memory
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    return graph

# Expose a singleton instance of the graph
agent_graph = create_agent_graph()
