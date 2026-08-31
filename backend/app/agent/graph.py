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

def call_model(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])
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
