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
CRITICAL RULE: NEVER call `filter_yarns_tool` more than once in the same conversation thread. If you already called it, reuse the Material Numbers you already found!

STEP 2: SCORING / RANKING
If `filter_yarns_tool` returns multiple yarns, you MUST score and rank them using `score_yarns_tool`.
However, BEFORE calling `score_yarns_tool`, determine the priority weights by following ONE of these 3 scenarios based on the user's prompt:

SCENARIO 1: The user provided exact numeric percentages (e.g. "70% price, 30% lead time").
-> Immediately call `score_yarns_tool` with those weights.

SCENARIO 2: The user mentioned priorities but with vague wording (e.g. "prioritize price", "consider lead time").
-> YOU MUST STOP AND ASK FOR PERMISSION EXACTLY AS FOLLOWS. 
CRITICAL RULE: DO NOT invent your own options (like Option A, B, C). You MUST use exactly Options 1, 2, 3, and 4 as written below:

"I found multiple yarns matching your criteria. To help you choose the best one, I can score and rank them. Based on your request, I suggest the following priority weights:
- [Your Predicted Attribute]: [Percentage]%
- [Your Predicted Attribute]: [Percentage]%

Please let me know how you would like to proceed by choosing one of the following options:
Option 1: Yes, use these percentages.
Option 2: Give me more options.
Option 3: Use equal percentages.
Option 4: I will provide my own percentages."

Wait for the user's reply. Do NOT call `score_yarns_tool` yet.

SCENARIO 3: The user provided NO priorities or attributes at all (e.g. "Find me elastane yarns").
-> YOU MUST STOP AND ASK THE USER TO SELECT ATTRIBUTES EXACTLY AS FOLLOWS. Do NOT deviate from this format:

"I found multiple yarns matching your criteria. To help you choose the best one, I can score and rank them. 
Please select which attributes you want to prioritize from the list below:
1. Price
2. Lead Time
3. Quality (Tenacity & Elongation)
4. Minimum Order Quantity (MOQ)
5. Hot Water Shrinkage
6. Tensile Strength
7. Thickness (Count dtex)

You can tell me which ones you care about, and optionally provide percentage weights (e.g., '1 and 2 equally' or 'Price 70%, Lead Time 30%'). If you just list the attributes, I will weight them equally."

Wait for the user's reply. Do NOT call `score_yarns_tool` yet.

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
