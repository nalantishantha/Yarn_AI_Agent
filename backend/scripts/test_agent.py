import sys
import os

# Add the backend root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from app.agent.graph import agent_graph

def main():
    print("--- Yarn Selection AI Agent (Automated Testing) ---\n")
    
    config = {"configurable": {"thread_id": "automated_test_thread"}}
    
    # --- INTERACTIVE CHAT (COMMENTED OUT) ---
    # while True:
    #     user_input = input("You: ")
    #     if user_input.lower() in ["quit", "exit"]:
    #         break
    #         
    #     if not user_input.strip():
    #         continue
    #         
    #     msg = HumanMessage(content=user_input)
    #     
    #     print("\n--- Execution Log ---")
    #     try:
    #         # Stream the graph execution
    #         for event in agent_graph.stream({"messages": [msg]}, config):
    #             pass # (Rest of the interactive execution logic was here)
    #     except Exception as e:
    #         pass
    
    # --- AUTOMATED TEST SCENARIOS ---
    test_scenarios = [
        # Scenario 1: Basic multi-filter (Type + Price)
        # "Find me a nylon yarn that costs less than 10 dollars.",
        
        # Scenario 2: Implicit NLP parsing (Time conversion: '4 weeks' -> 28 days) + Location
        # "I need a yarn from South Korea with a lead time of less than 4 weeks.",
        
        # Scenario 3: Highly specific numerical filtering
        # "Do you have any elastane yarn with a count dtex greater than 150?",
        
        # Scenario 4: Exact string matching & equality constraints (Testing TPM/PPM OR logic and hyphen normalization)
        # "I am looking for a semi dull yarn with a twist per metre of exactly 90.",
        
        # Scenario 5: Complex composite filtering (Supplier + Price + MOQ limits)
        # "Find a yarn from Fulgar Lanka that costs less than 15 dollars and has a MOQ under 30kg.",
        
        # Scenario 6: FDY/DTY String Mapping
        # "I need a draw textured yarn with a price under 15 dollars.",
        
        # Scenario 7: Tenacity and Elongation (Testing technical float specs)
        "Find me a yarn with a breaking tenacity greater than 35 and elongation over 50.",
        
        # Scenario 8: Shrinkage constraint (Testing negative numbers that exist in DB e.g. -5.15)
        # "Are there any yarns with hot water shrinkage less than -5?",
        
        # Scenario 9: Supplier partial text match
        # "Do you have anything from Hyosung?",
        
        # Scenario 10: Extreme constraints (Testing graceful failure on 0 results)
        # "Find me an elastane yarn from Sri Lanka that costs less than 1 dollar."
    ]
    
    for i, user_input in enumerate(test_scenarios, 1):
        print(f"\n\n==================================================")
        print(f"SCENARIO {i}: {user_input}")
        print(f"==================================================")
        
        msg = HumanMessage(content=user_input)
        
        print("\n--- Execution Log ---")
        try:
            # Stream the graph execution
            for event in agent_graph.stream({"messages": [msg]}, config):
                for node_name, value in event.items():
                    if node_name == "agent":
                        msg_obj = value["messages"]
                        
                        if hasattr(msg_obj, "tool_calls") and msg_obj.tool_calls:
                            print(f"\n[LLM ACTION] The LLM decided to call a tool:")
                            for tc in msg_obj.tool_calls:
                                print(f"  -> Tool Name: {tc['name']}")
                                print(f"  -> Arguments: {tc['args']}")
                                
                        if msg_obj.content:
                            print(f"\n[LLM MESSAGE] {msg_obj.content}")
                            
                    elif node_name == "tools":
                        # value["messages"] is a list, the last message is the tool response
                        tool_msg = value["messages"][-1]
                        print(f"\n[TOOL EXECUTION] The tool finished querying the database.")
                        print(f"  -> Returned Data to LLM:\n{tool_msg.content}")
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                print("\n[ERROR] Gemini API Rate Limit Exceeded (Free Tier limit reached).")
            else:
                print(f"\n[ERROR] An unexpected error occurred:\n{e}")

if __name__ == "__main__":
    main()
