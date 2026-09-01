import sys
import os

# Add the project root to the python path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.messages import HumanMessage, ToolMessage
from app.agent.graph import agent_graph

def run_interactive_scenario(scenario_name, initial_prompt, thread_id):
    print(f"\n{'='*70}\nSCENARIO: {scenario_name}\n{'='*70}")
    print("Type 'next' to move to the next scenario, or 'quit' to exit completely.\n")
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Send the initial prompt
    print(f"You (Auto-Prompt): {initial_prompt}\n")
    user_input = initial_prompt
    
    while True:
        print("--- Execution Log ---\n")
        
        # Invoke agent
        response = agent_graph.invoke({"messages": [HumanMessage(content=user_input)]}, config)
        
        # Trace the messages to see tool calls
        for msg in response["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for call in msg.tool_calls:
                    print(f"[LLM ACTION] The LLM decided to call a tool:")
                    print(f"  -> Tool Name: {call['name']}")
                    print(f"  -> Arguments: {call['args']}\n")
            elif isinstance(msg, ToolMessage):
                print(f"[TOOL EXECUTION] The tool {msg.name} finished.")
                print(f"  -> Returned Data to LLM:\n{str(msg.content)[:500]}...\n")
        
        # Print LLM Message
        final_msg = response["messages"][-1]
        print(f"[LLM MESSAGE] {final_msg.content}\n")
        print("-" * 30 + "\n")
        
        # Ask for user input
        user_input = input("You: ").strip()
        if user_input.lower() == 'next':
            break
        if user_input.lower() in ['quit', 'exit']:
            print("Exiting tests.")
            sys.exit(0)

if __name__ == "__main__":
    print("--- Yarn Selection AI Agent (Scoring Testing - Interactive) ---\n")
    
    scenarios = [
        ("Branch 1: Exact Percentages", "Find me elastane yarns. I care about price (70%) and lead time (30%)."),
        ("Branch 2: Vague Priority -> Accept Predicted (Option 1)", "Find me cotton yarns and prioritize price."),
        ("Branch 2: Vague Priority -> Custom Percentages (Option 4)", "Find me viscose yarns and prioritize moq."),
        ("Branch 3: No Priorities -> Select Attributes", "Find me polyester yarns."),
        ("Special: Quality Composite Score", "Find me yarns from South Korea and prioritize Quality.")
    ]
    
    for i, (name, prompt) in enumerate(scenarios):
        run_interactive_scenario(name, prompt, f"thread_scenario_{i}")
        
    print("\nAll scenarios completed!")
