from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The state for our AI Agent graph.
    messages: A list of chat messages, appended to automatically.
    """
    messages: Annotated[list, add_messages]
