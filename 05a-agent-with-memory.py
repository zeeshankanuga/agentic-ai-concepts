#!/usr/bin/env python3
"""
Level 5a: Agent with Conversation Memory

NEW CONCEPTS INTRODUCED:
- Conversation history management (messages list)
- Context window awareness (truncating old messages)
- System prompt + user/assistant message roles
- Session persistence concept (in-memory)

ARCHITECTURE EVOLUTION:
Level 4 (agent_with_mcp.py): Single request/response, no memory
Level 5a (this file): Conversation loop with message history
Level 5b: Async agent with proper event loop
Level 5c: RAG integration
Level 5d: LangGraph workflow
Level 5e: Class-based tools
Level 5f: Multi-step reasoning
Level 6: Full system (kubernetes-agent.py)
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import asyncio


SYSTEM_PROMPT = """
You are a Docker expert. Explain things in 1-2 lines max.
You don't overthink, hallucinate, or keep reasoning in loops.
You reason and act according to user prompt.

Your tasks:
1. Tell about errors (what went wrong)
2. Tell about root cause (likely cause)
3. Tell about the fix/solution (short)
"""


async def main():
    # Connect to MCP server (same as Level 4)
    client = MultiServerMCPClient(
        {
            "docker-mcp": {
                "transport": "stdio",
                "command": "python3",
                "args": ["03-mcp_server.py"]
            }
        }
    )
    
    tools = await client.get_tools()
    print(f"✓ Discovered {len(tools)} tools from MCP server: {[t.name for t in tools]}")
    
    llm = ChatOllama(
        model="gemma4:e4b",
        temperature=0.8,
        system=SYSTEM_PROMPT
    )
    
    agent = create_agent(llm, tools)
    
    # ============================================================
    # NEW: Conversation History (Message List)
    # ============================================================
    # In Level 4, each request was independent: agent.invoke({"messages": [user_msg]})
    # Here we maintain a list of ALL messages across the conversation.
    # This gives the agent MEMORY - it remembers what was discussed before.
    
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    
    print("\n" + "="*60)
    print("🤖 Docker Agent with Memory (Level 5a)")
    print("   Type 'exit' to quit, 'clear' to reset memory")
    print("="*60 + "\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        
        if user_input.lower() == "clear":
            messages = [SystemMessage(content=SYSTEM_PROMPT)]
            print("🧹 Memory cleared!\n")
            continue
        
        if not user_input:
            continue
        
        # Add user message to history
        messages.append(HumanMessage(content=user_input))
        
        # ============================================================
        # CONTEXT WINDOW MANAGEMENT
        # ============================================================
        # LLMs have a maximum context window (e.g., 8k, 32k, 128k tokens).
        # If conversation gets too long, we must truncate older messages.
        # Strategy: Keep system prompt + last N messages (sliding window).
        
        MAX_MESSAGES = 20  # Keep last 20 messages (10 exchanges)
        if len(messages) > MAX_MESSAGES:
            # Keep system message + last (MAX_MESSAGES - 1) messages
            messages = [messages[0]] + messages[-(MAX_MESSAGES - 1):]
            print(f"   [Context trimmed to last {MAX_MESSAGES - 1} messages]")
        
        # Invoke agent with FULL conversation history
        try:
            response = await agent.ainvoke({"messages": messages})
            
            # Extract assistant's response
            assistant_message = response['messages'][-1]
            print(f"Agent: {assistant_message.content}\n")
            
            # Add assistant response to history for next turn
            messages.append(assistant_message)
            
        except Exception as e:
            print(f"❌ Error: {e}\n")
            # Remove the failed user message from history
            messages.pop()


if __name__ == "__main__":
    asyncio.run(main())