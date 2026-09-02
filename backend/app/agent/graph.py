import os
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from app.agent.state import AgentState
from app.agent.tools import AGENT_TOOLS

# Make sure env is loaded
load_dotenv()

# Initialize OpenAI LLM (Primary)
# Requires OPENAI_API_KEY in .env
openai_llm = ChatOpenAI(model="gpt-4o-mini")
openai_with_tools = openai_llm.bind_tools(AGENT_TOOLS, parallel_tool_calls=False)

# Use OpenAI as the sole LLM
llm_with_tools = openai_with_tools

from langchain_core.messages import SystemMessage

SYSTEM_PROMPT = """You are a Yarn Selection AI Agent.
You MUST follow this EXACT sequential flow. CRITICAL RULE: NEVER call multiple tools in parallel at the same time. Always wait for the result of one tool before calling the next.

STEP 1: DATABASE POLICIES (WRITE)
Check if the user stated any *long-term* policies (e.g., "blacklist supplier Z for all future orders", "from now on").
If so, call `add_sourcing_constraint_tool` to propose writing it to the database.
CRITICAL RULE: NEVER call `add_sourcing_constraint_tool` for one-off policies that only apply to the current search (e.g., "for this order", "just for this query", "this time", "for this specific order"). If the user states a one-off policy, DO NOT use this tool; instead, you will pass that constraint to `apply_policies_tool` in Step 4.

STEP 2: FILTERING
Call `filter_yarns_tool` with the exact attributes the user mentioned.
Wait for the database to return the matching yarns. 
CRITICAL RULE: Do not re-call with unchanged criteria, but DO re-call whenever the user changes, adds, or removes a filter attribute mid-conversation.

STEP 3: SCORING / RANKING
If `filter_yarns_tool` returns multiple yarns, you MUST score and rank them using `score_yarns_tool`.
Before calling `score_yarns_tool`, note that the keys for scoring weights differ from filtering parameters. You MUST use exactly these keys for scoring weights:
- Price -> Price
- Lead Time -> lt_max_days
- Quality (Tenacity & Elongation) -> Quality
- Minimum Order Quantity (MOQ) -> moq_max
- Hot Water Shrinkage -> Hot_Water_Shrinkage
- Tensile Strength -> Tensile_Strength
- Thickness (Count dtex) -> Count_dtex

Determine the priority weights by following ONE of these 3 scenarios based on the user's prompt:

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
Sometimes user will give few attributes with exact percentages and tell equally divide remaining among other attributes.. For this case you have to calculate weights for all attributes including remaining ones. total weights is always 100%...

Wait for the user's reply. Do NOT call `score_yarns_tool` yet.

STEP 4: POLICIES & FINAL SYNTHESIS
Once you have your candidate list (whether or not scoring happened), call
`apply_policies_tool` with the candidate yarn_ids, their current scores (use 0.0 for
each if scoring was skipped, e.g. if exactly 1 candidate was returned by filtering), and any one-off constraints the user stated for this
query only (see STEP 1 for the long-term vs. one-off distinction).
Never compute policy restrictions or boosts yourself — always use this tool.
If `all_excluded_by_policy` comes back true, tell the user plainly that no yarn
satisfies both the technical requirements and the active sourcing policy, and that
this has been flagged for manual review — do not silently drop the request.
Otherwise, present the final ranked list, and explicitly state any exclusions or
boosts that were applied and why, using the `excluded` / `applied_boosts` info
returned by the tool.
"""

from langchain_core.messages import SystemMessage, ToolMessage

def call_model(state: AgentState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": response}

def reject_mixed_tool_batch(state: AgentState):
    messages = state.get("messages", [])
    last_message = messages[-1]
    tool_messages = []
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
                content="Error: You attempted to call multiple tools in parallel where one or more are sensitive operations. This is not allowed. Please retry calling the tools one at a time, strictly sequentially."
            ))
    return {"messages": tool_messages}

def create_agent_graph():
    """
    Creates and compiles the LangGraph for the Yarn Agent.
    """
    builder = StateGraph(AgentState)
    
    # Split tools into safe and sensitive for human-in-the-loop
    safe_tools = [t for t in AGENT_TOOLS if t.name != "add_sourcing_constraint_tool"]
    sensitive_tools = [t for t in AGENT_TOOLS if t.name == "add_sourcing_constraint_tool"]
    
    # Add Nodes
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(safe_tools))
    builder.add_node("sensitive_tools", ToolNode(sensitive_tools))
    builder.add_node("reject_mixed_tool_batch", reject_mixed_tool_batch)
    
    # Add Edges
    builder.add_edge(START, "agent")
    
    def route_tools(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return END
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            is_sensitive = False
            is_safe = False
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "add_sourcing_constraint_tool":
                    is_sensitive = True
                else:
                    is_safe = True
            
            if is_sensitive and is_safe:
                return "reject_mixed_tool_batch"
            elif is_sensitive:
                return "sensitive_tools"
            else:
                return "tools"
        return END

    # Conditional edge: route to appropriate tool node
    builder.add_conditional_edges("agent", route_tools)
    
    builder.add_edge("tools", "agent")
    builder.add_edge("sensitive_tools", "agent")
    builder.add_edge("reject_mixed_tool_batch", "agent")
    
    # Compile with memory
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory, interrupt_before=["sensitive_tools"])
    
    return graph

# Expose a singleton instance of the graph
agent_graph = create_agent_graph()
