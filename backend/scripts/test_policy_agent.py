import sys
import os

# Add the project root to the python path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.messages import HumanMessage, ToolMessage
from app.agent.graph import agent_graph

def run_interactive_scenario(scenario_name, prompts, thread_id):
    print(f"\n{'='*70}\nSCENARIO: {scenario_name}\n{'='*70}")
    print("Type 'next' to move to the next scenario, or 'quit' to exit completely.\n")
    
    config = {"configurable": {"thread_id": thread_id}}
    
    prompt_queue = list(prompts)
    
    # Send the initial prompt
    user_input = prompt_queue.pop(0)
    print(f"You (Auto-Prompt): {user_input}\n")
    
    while True:
        print("--- Execution Log ---\n")
        
        # Invoke agent. If it was interrupted, user_input might be empty or 'y' which we handle below.
        if user_input:
            messages = [HumanMessage(content=user_input)]
        else:
            messages = None # Resuming from interrupt
            
        response = agent_graph.invoke({"messages": messages} if messages else None, config)
        
        # Check if we hit an interrupt
        state = agent_graph.get_state(config)
        if state.next and "sensitive_tools" in state.next:
            print("\n[!] INTERRUPT TRIGGERED: The agent wants to write a policy to the database.")
            
            # Find the tool call that triggered this
            last_msg = state.values["messages"][-1]
            if hasattr(last_msg, "tool_calls"):
                for call in last_msg.tool_calls:
                    if call["name"] == "add_sourcing_constraint_tool":
                        print(f"    Proposed Policy: {call['args']}")
            
            confirm = input("\nApprove writing this policy to the database? (y/n): ").strip().lower()
            if confirm == 'y':
                print("Approving policy... resuming execution.")
                user_input = None # will trigger resume
                continue
            else:
                print("Rejecting policy... sending rejection to agent.")
                # Get the tool call ID to construct the ToolMessage
                tool_call_id = None
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
                
                user_input = None # trigger resume so the graph continues from after the tool
                continue
                
        # Trace the messages to see tool calls (skip if just resuming and already printed)
        if response and "messages" in response:
            # We only want to print new messages, but for simplicity we'll just look at the last few
            # This is a basic log for the terminal test
            for msg in response["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for call in msg.tool_calls:
                        print(f"[LLM ACTION] The LLM decided to call a tool:")
                        print(f"  -> Tool Name: {call['name']}")
                        print(f"  -> Arguments: {call['args']}\n")
                elif isinstance(msg, ToolMessage):
                    print(f"[TOOL EXECUTION] The tool {msg.name} finished.")
                    print(f"  -> Returned Data to LLM:\n{str(msg.content)[:500]}...\n")
            
            # Print Final LLM Message
            final_msg = response["messages"][-1]
            if not hasattr(final_msg, "tool_calls") or not final_msg.tool_calls:
                print(f"[LLM MESSAGE] {final_msg.content}\n")
        
        print("-" * 30 + "\n")
        
        # Ask for user input
        if prompt_queue:
            user_input = prompt_queue.pop(0)
            print(f"You (Auto-Follow-Up): {user_input}\n")
            continue
            
        user_input = input("You: ").strip()
        if user_input.lower() == 'next':
            break
        if user_input.lower() in ['quit', 'exit']:
            print("Exiting tests.")
            sys.exit(0)

if __name__ == "__main__":
    print("--- Yarn Selection AI Agent (Policy Testing - Interactive) ---\n")
    
    scenarios = [
        ("Parallel Tool Call (Reject-and-Retry)", ["Find me cotton yarns. Oh, and blacklist Hyosung for all orders."]),
        ("Single Candidate Test", ["Find me exactly the cotton yarn with price $5.34 from China. (Expect 0 or 1 result)"]),
        ("Typo'd Key Error Test", ["Find me cotton yarns. Score them with 50% Price and 50% Thicknes (with a typo)."]),
        ("Filter Recall (Mid-conversation change)", ["Find me cotton yarns.", "Actually, make sure they are under $8."]),
        ("Menu Picks Mapping (MOQ & Thickness)", ["Find me elastane yarns.", "Prioritize MOQ and Thickness equally."]),
        ("Multiple Candidates + Boost + Hard Restrict", ["Find me cotton yarns.", "Option 3", "Prefer Hyosung for this order, and absolutely DO NOT use Fulgar Lanka."]),
    ]
    
    for i, (name, prompts) in enumerate(scenarios):
        run_interactive_scenario(name, prompts, f"thread_policy_scenario_{i}")
        
    print("\nAll scenarios completed!")
