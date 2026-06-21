#!/usr/bin/env python3
"""
Level 5d: LangGraph Basics - Simple Multi-Node Workflow

NEW CONCEPTS INTRODUCED:
- LangGraph StateGraph (workflow orchestration)
- TypedDict for structured state management
- Nodes (individual processing steps)
- Edges (connections between nodes)
- Conditional edges (branching logic)
- State passing between nodes (shared memory)
- Graph compilation and invocation

ARCHITECTURE EVOLUTION:
Level 5c: RAG with in-memory knowledge base
Level 5d (this file): LangGraph workflow orchestration (2-3 nodes)
Level 5e: Class-based tools with structured output
Level 5f: Multi-step reasoning with explicit steps
Level 6: Full system (kubernetes-agent.py) - 5 nodes, RAG, tools, MCP
"""

from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from typing import TypedDict, List, Dict, Any, Optional, Literal
import asyncio
import json


# =============================================================================
# STEP 1: DEFINE STATE (TypedDict - Shared Memory Across Nodes)
# =============================================================================

class AgentState(TypedDict):
    """
    LangGraph State - The shared memory that flows through ALL nodes.
    
    Each node can READ and WRITE to this state.
    This is how data passes between nodes in the graph.
    """
    # Input
    user_query: str                    # Original user question
    
    # Processing state (filled by nodes)
    rewritten_query: str               # Optimized query for retrieval
    retrieved_context: str             # Knowledge from RAG
    tool_calls: List[Dict[str, Any]]   # Tools the LLM decided to call
    tool_results: List[Dict[str, Any]] # Results from tool execution
    
    # Output
    final_answer: str                  # Final response to user
    
    # Metadata
    error: Optional[str]               # Any error messages
    step: str                          # Current step for debugging


# =============================================================================
# STEP 2: DEFINE NODES (Individual Processing Steps)
# =============================================================================

SYSTEM_PROMPT = """You are a Docker expert. Be concise (1-2 lines per point)."""


# NODE 1: Query Rewriter
# Purpose: Optimize user query for better retrieval
def rewrite_query(state: AgentState) -> AgentState:
    """
    Node 1: Rewrite user query for better search/retrieval.
    
    CONCEPT: User queries are often vague. Rewriting adds context
    and keywords for better semantic search.
    """
    print(f"🔄 [Node: rewrite_query] Processing: {state['user_query'][:50]}...")
    
    query = state["user_query"]
    
    # Simple rewrite: add Docker context
    rewritten = f"Docker troubleshooting: {query}"
    
    return {
        **state,
        "rewritten_query": rewritten,
        "step": "rewrite_query"
    }


# NODE 2: Knowledge Retrieval (Simulated RAG)
# Purpose: Get relevant context from knowledge base
def retrieve_knowledge(state: AgentState) -> AgentState:
    """
    Node 2: Retrieve relevant knowledge for the query.
    
    CONCEPT: This simulates RAG retrieval. In production, this would
    query a vector database (ChromaDB, Pinecone, etc.).
    """
    print(f"📚 [Node: retrieve] Searching for: {state['rewritten_query'][:50]}...")
    
    query = state["rewritten_query"].lower()
    
    # Simple keyword-based knowledge base (for demo)
    knowledge = {
        "container exits": "Container exits immediately = main process finishes. Fix: Use foreground process in CMD/ENTRYPOINT.",
        "port allocated": "Port already allocated = another process using port. Fix: docker ps to find conflict, use different port.",
        "image pull": "ImagePullBackOff/ErrImagePull = wrong name/tag or private registry. Fix: Verify name, docker login, check rate limits.",
        "permission denied": "Permission denied on volume mount = SELinux/AppArmor/permissions. Fix: Use :Z suffix, check host perms.",
        "disk space": "Out of disk space = unused images/containers/volumes. Fix: docker system prune -a.",
        "restart loop": "Container restarting = app crashes or health check fails. Fix: Check logs, docker inspect for OOMKilled.",
        "logs": "View logs: docker logs <container>, -f to follow, --tail N for last N lines, --since 1h for time range.",
        "inspect": "Inspect container: docker inspect <container> for full config, docker top for processes.",
        "exec": "Execute in container: docker exec -it <container> sh for shell, docker exec <container> cmd for command.",
        "stats": "Resource usage: docker stats <container> for live CPU/memory, --no-stream for snapshot.",
        "compose": "Compose: docker compose up -d, down, ps, logs -f, exec <service> sh.",
    }
    
    # Find matching knowledge
    matches = []
    for keyword, answer in knowledge.items():
        if keyword in query:
            matches.append(f"[{keyword}] {answer}")
    
    if matches:
        context = "\n".join(matches[:3])  # Top 3 matches
    else:
        context = "No specific knowledge found for this query."
    
    return {
        **state,
        "retrieved_context": context,
        "step": "retrieve"
    }


# NODE 3: Decision Maker
# Purpose: LLM decides whether to use tools or answer directly
def decide_action(state: AgentState) -> AgentState:
    """
    Node 3: LLM decides next action - use tools or answer directly.
    
    CONCEPT: The agent reasons about whether it needs live data (tools)
    or can answer from knowledge + reasoning.
    """
    print(f"🤔 [Node: decide] Making decision...")
    
    llm = ChatOllama(model="gemma4:e4b", temperature=0, system=SYSTEM_PROMPT)
    
    # Available tools description
    tools_desc = """
Available Docker Tools:
- running_containers(): List all running container IDs
- container_logs(container_name): Get last 10 lines of container logs
"""
    
    prompt = f"""You are a Docker expert. Decide the next action.

RETRIEVED KNOWLEDGE:
{state['retrieved_context']}

{tools_desc}

USER QUERY: {state['user_query']}

RESPOND WITH JSON ONLY:
{{
  "action": "use_tools" | "answer_directly",
  "tool": "tool_name_if_needed",
  "args": {{"param": "value"}},
  "reasoning": "why this action"
}}"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        decision = json.loads(response.content)
        
        print(f"   Decision: {decision['action']} - {decision.get('reasoning', '')}")
        
        if decision["action"] == "use_tools":
            return {
                **state,
                "tool_calls": [{"tool": decision["tool"], "args": decision["args"]}],
                "step": "decide"
            }
        else:
            return {
                **state,
                "final_answer": decision.get("reasoning", "Answered from knowledge."),
                "step": "decide"
            }
    except Exception as e:
        print(f"   ❌ Decision error: {e}")
        return {
            **state,
            "final_answer": f"Error in decision: {e}",
            "error": str(e),
            "step": "decide"
        }


# NODE 4: Tool Executor
# Purpose: Execute the decided tool calls
def execute_tools(state: AgentState) -> AgentState:
    """
    Node 4: Execute tool calls on Docker.
    
    CONCEPT: This runs the actual tools. In Level 6, this uses
    Kubernetes API directly. Here we use subprocess for Docker CLI.
    """
    import subprocess
    
    print(f"🔧 [Node: execute_tools] Running {len(state.get('tool_calls', []))} tool(s)...")
    
    results = []
    
    for call in state.get("tool_calls", []):
        tool_name = call["tool"]
        args = call["args"]
        
        print(f"   Calling: {tool_name}({args})")
        
        try:
            if tool_name == "running_containers":
                result = subprocess.run(
                    ["docker", "ps", "-q"],
                    capture_output=True, text=True
                )
                results.append({
                    "tool": tool_name,
                    "result": {"containers": result.stdout.strip().split('\n') if result.stdout else []}
                })
            
            elif tool_name == "container_logs":
                container = args.get("container_name", "")
                result = subprocess.run(
                    ["docker", "logs", "--tail", "10", container],
                    capture_output=True, text=True
                )
                results.append({
                    "tool": tool_name,
                    "result": {"logs": result.stdout, "container": container}
                })
            
            else:
                results.append({
                    "tool": tool_name,
                    "result": {"error": f"Unknown tool: {tool_name}"}
                })
        
        except Exception as e:
            results.append({
                "tool": tool_name,
                "result": {"error": str(e)}
            })
    
    return {
        **state,
        "tool_results": results,
        "step": "execute_tools"
    }


# NODE 5: Synthesizer
# Purpose: Combine everything into final answer
def synthesize(state: AgentState) -> AgentState:
    """
    Node 5: Synthesize final answer from knowledge + tool results.
    
    CONCEPT: This is where the agent "thinks" and produces the
    human-readable response using all gathered information.
    """
    print(f"✨ [Node: synthesize] Generating final answer...")
    
    llm = ChatOllama(model="gemma4:e4b", temperature=0, system=SYSTEM_PROMPT)
    
    # Format tool results
    tool_results_text = ""
    for r in state.get("tool_results", []):
        tool_results_text += f"\nTool {r['tool']} result: {json.dumps(r['result'], indent=2)}"
    
    prompt = f"""You are a Docker expert. Provide a clear, concise answer.

RETRIEVED KNOWLEDGE:
{state['retrieved_context']}

TOOL RESULTS:
{tool_results_text if tool_results_text else "No tools were used."}

ORIGINAL QUESTION: {state['user_query']}

Answer in 1-3 bullet points. Cite knowledge sources [like this] and tool results."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {
        **state,
        "final_answer": response.content,
        "step": "synthesize"
    }


# =============================================================================
# STEP 3: DEFINE ROUTING (Conditional Edges)
# =============================================================================

def route_after_decide(state: AgentState) -> Literal["execute_tools", "synthesize"]:
    """
    Router: Decide next node based on state.
    
    CONCEPT: Conditional edges enable branching. The router reads
    state and returns the NAME of the next node.
    """
    if state.get("tool_calls"):
        return "execute_tools"
    return "synthesize"


# =============================================================================
# STEP 4: BUILD THE GRAPH
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph workflow.
    
    GRAPH STRUCTURE:
    
    rewrite_query → retrieve → decide_action → (execute_tools →) synthesize
                                                    ↑              │
                                                    └──────────────┘
    
    This is a classic pattern: retrieve → decide → act → synthesize
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("retrieve", retrieve_knowledge)
    workflow.add_node("decide_action", decide_action)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("synthesize", synthesize)
    
    # Add edges (the flow)
    workflow.set_entry_point("rewrite_query")
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("retrieve", "decide_action")
    
    # Conditional edge: decide_action → execute_tools OR synthesize
    workflow.add_conditional_edges(
        "decide_action",
        route_after_decide,
        {
            "execute_tools": "execute_tools",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_edge("execute_tools", "synthesize")
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()


# =============================================================================
# STEP 5: RUN THE AGENT
# =============================================================================

async def run_agent(query: str) -> Dict[str, Any]:
    """Run the LangGraph agent on a single query."""
    graph = build_graph()
    
    # Initial state
    initial_state: AgentState = {
        "user_query": query,
        "rewritten_query": "",
        "retrieved_context": "",
        "tool_calls": [],
        "tool_results": [],
        "final_answer": "",
        "error": None,
        "step": "start"
    }
    
    print(f"\n{'='*60}")
    print(f"🚀 Running LangGraph Agent on: {query}")
    print(f"{'='*60}\n")
    
    # Invoke the graph (this runs all nodes in order)
    final_state = graph.invoke(initial_state)
    
    print(f"\n{'='*60}")
    print(f"✅ Final Answer:")
    print(f"{final_state['final_answer']}")
    print(f"{'='*60}\n")
    
    return final_state


async def interactive_mode():
    """Interactive conversation with the LangGraph agent."""
    graph = build_graph()
    
    print("\n" + "="*60)
    print("🤖 LangGraph Docker Agent (Level 5d)")
    print("   Workflow: rewrite → retrieve → decide → (tools →) synthesize")
    print("   Type 'exit' to quit")
    print("="*60 + "\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() == "exit":
            break
        
        # Run graph
        initial_state: AgentState = {
            "user_query": user_input,
            "rewritten_query": "",
            "retrieved_context": "",
            "tool_calls": [],
            "tool_results": [],
            "final_answer": "",
            "error": None,
            "step": "start"
        }
        
        try:
            final_state = graph.invoke(initial_state)
            print(f"Agent: {final_state['final_answer']}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def demo():
    """Run demo queries."""
    test_queries = [
        "How many containers are running?",
        "Why does my container exit immediately?",
        "Show me logs for container nginx",
        "How to fix port already allocated error?",
    ]
    
    for query in test_queries:
        await run_agent(query)


async def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await demo()
    else:
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())