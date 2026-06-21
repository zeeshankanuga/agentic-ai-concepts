#!/usr/bin/env python3
"""
Level 5b: Async Agent with Proper Event Loop & Streaming

NEW CONCEPTS INTRODUCED:
- Async/await patterns throughout (not just at top level)
- Streaming responses token-by-token
- Concurrent tool execution with asyncio.gather
- Proper error handling with try/except in async context
- Async context managers for resource cleanup
- Background tasks for non-blocking operations

ARCHITECTURE EVOLUTION:
Level 5a: Sync conversation loop with memory
Level 5b (this file): Full async patterns, streaming, concurrency
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
from langchain_core.callbacks import AsyncCallbackHandler
import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager


SYSTEM_PROMPT = """
You are a Docker expert. Explain things in 1-2 lines max.
You don't overthink, hallucinate, or keep reasoning in loops.
You reason and act according to user prompt.

Your tasks:
1. Tell about errors (what went wrong)
2. Tell about root cause (likely cause)
3. Tell about the fix/solution (short)
"""


@dataclass
class AgentMetrics:
    """Track performance metrics for the agent."""
    total_requests: int = 0
    total_tokens: int = 0
    total_time: float = 0.0
    tool_calls: int = 0
    errors: int = 0
    
    def record_request(self, duration: float, tokens: int = 0):
        self.total_requests += 1
        self.total_time += duration
        self.total_tokens += tokens
    
    def record_tool_call(self):
        self.tool_calls += 1
    
    def record_error(self):
        self.errors += 1
    
    def summary(self) -> str:
        avg_time = self.total_time / self.total_requests if self.total_requests > 0 else 0
        return (f"Requests: {self.total_requests} | "
                f"Avg Time: {avg_time:.2f}s | "
                f"Tools: {self.tool_calls} | "
                f"Errors: {self.errors}")


class StreamingCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming token-by-token responses."""
    
    def __init__(self):
        self.tokens: List[str] = []
        self.start_time: Optional[float] = None
    
    async def on_llm_start(self, *args, **kwargs):
        self.start_time = time.time()
        self.tokens = []
        print("Agent: ", end="", flush=True)
    
    async def on_llm_new_token(self, token: str, **kwargs):
        self.tokens.append(token)
        print(token, end="", flush=True)
    
    async def on_llm_end(self, *args, **kwargs):
        duration = time.time() - self.start_time if self.start_time else 0
        print(f"\n   [Streamed {len(self.tokens)} tokens in {duration:.2f}s]")
    
    async def on_tool_start(self, *args, **kwargs):
        print(f"\n   🔧 Calling tool...")
    
    async def on_tool_end(self, *args, **kwargs):
        print(f"   ✓ Tool completed")


class AsyncDockerAgent:
    """
    Async-first agent with proper resource management.
    
    Key async patterns demonstrated:
    1. __aenter__/__aexit__ for context management
    2. asyncio.gather for concurrent operations
    3. Streaming callbacks for real-time output
    4. Proper exception handling in async context
    5. Background tasks for non-blocking work
    """
    
    def __init__(self, model: str = "gemma4:e4b", temperature: float = 0.8):
        self.model = model
        self.temperature = temperature
        self.client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.metrics = AgentMetrics()
        self._background_tasks: List[asyncio.Task] = []
    
    async def __aenter__(self) -> "AsyncDockerAgent":
        """Async context manager entry - initialize connections."""
        print("🔌 Connecting to MCP server...")
        self.client = MultiServerMCPClient({
            "docker-mcp": {
                "transport": "stdio",
                "command": "python3",
                "args": ["03-mcp_server.py"]
            }
        })
        
        tools = await self.client.get_tools()
        print(f"✓ Discovered {len(tools)} tools: {[t.name for t in tools]}")
        
        llm = ChatOllama(
            model=self.model,
            temperature=self.temperature,
            system=SYSTEM_PROMPT,
            callbacks=[StreamingCallbackHandler()]  # Enable streaming
        )
        
        self.agent = create_agent(llm, tools)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        print("\n🧹 Cleaning up...")
        
        # Cancel any background tasks
        for task in self._background_tasks:
            task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Close MCP client if it has a close method
        if self.client and hasattr(self.client, 'close'):
            await self.client.close()
        
        print(f"📊 Session metrics: {self.metrics.summary()}")
    
    async def process_message(self, messages: List) -> AIMessage:
        """Process a single message with full async stack."""
        start_time = time.time()
        
        try:
            # ainvoke is async - doesn't block event loop
            response = await self.agent.ainvoke({"messages": messages})
            assistant_msg = response['messages'][-1]
            
            duration = time.time() - start_time
            self.metrics.record_request(duration)
            
            # Count tool calls in response
            for msg in response['messages']:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    self.metrics.record_tool_call()
            
            return assistant_msg
            
        except Exception as e:
            self.metrics.record_error()
            raise
    
    async def run_concurrent_queries(self, queries: List[str]) -> List[str]:
        """
        Demonstrate concurrent execution - run multiple queries in parallel.
        This is only possible with proper async architecture!
        """
        print(f"\n⚡ Running {len(queries)} queries concurrently...")
        
        async def single_query(query: str) -> str:
            messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
            response = await self.agent.ainvoke({"messages": messages})
            return response['messages'][-1].content
        
        # asyncio.gather runs all coroutines concurrently!
        results = await asyncio.gather(*[single_query(q) for q in queries], return_exceptions=True)
        
        # Handle any exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(f"❌ Error: {result}")
            else:
                processed.append(result)
        
        return processed
    
    def start_background_task(self, coro):
        """Start a fire-and-forget background task."""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        return task


@asynccontextmanager
async def create_agent_context(model: str = "gemma4:e4b"):
    """Convenience async context manager for quick scripts."""
    agent = AsyncDockerAgent(model=model)
    try:
        await agent.__aenter__()
        yield agent
    finally:
        await agent.__aexit__(None, None, None)


async def interactive_mode(agent: AsyncDockerAgent):
    """Run interactive conversation loop with memory."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    MAX_MESSAGES = 20
    
    print("\n" + "="*60)
    print("🤖 Async Docker Agent (Level 5b) - Streaming & Concurrent")
    print("   Commands: 'exit', 'clear', 'metrics', 'concurrent <query1> | <query2>'")
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
        
        if user_input.lower() == "clear":
            messages = [SystemMessage(content=SYSTEM_PROMPT)]
            print("🧹 Memory cleared!\n")
            continue
        
        if user_input.lower() == "metrics":
            print(f"📊 {agent.metrics.summary()}\n")
            continue
        
        # Handle concurrent query command: "concurrent query1 | query2 | query3"
        if user_input.lower().startswith("concurrent "):
            queries = [q.strip() for q in user_input[11:].split("|")]
            results = await agent.run_concurrent_queries(queries)
            for i, (q, r) in enumerate(zip(queries, results)):
                print(f"\n--- Query {i+1}: {q} ---")
                print(r)
            print()
            continue
        
        # Normal conversation
        messages.append(HumanMessage(content=user_input))
        
        # Context window management
        if len(messages) > MAX_MESSAGES:
            messages = [messages[0]] + messages[-(MAX_MESSAGES - 1):]
            print(f"   [Context trimmed to last {MAX_MESSAGES - 1} messages]")
        
        try:
            assistant_msg = await agent.process_message(messages)
            print()  # Newline after streaming
            messages.append(assistant_msg)
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            messages.pop()  # Remove failed user message


async def demo_concurrent_execution():
    """Demonstrate concurrent query execution."""
    print("\n" + "="*60)
    print("🎯 DEMO: Concurrent Query Execution")
    print("="*60)
    
    async with create_agent_context() as agent:
        queries = [
            "How many containers are running?",
            "What Docker images do I have?",
            "Show me container status",
        ]
        
        start = time.time()
        results = await agent.run_concurrent_queries(queries)
        elapsed = time.time() - start
        
        print(f"\n⏱️  Total time for {len(queries)} concurrent queries: {elapsed:.2f}s")
        print(f"   (Sequential would take ~{elapsed * len(queries):.2f}s)")
        
        for q, r in zip(queries, results):
            print(f"\n📝 {q}")
            print(f"   {r[:100]}...")


async def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await demo_concurrent_execution()
        return
    
    async with create_agent_context() as agent:
        await interactive_mode(agent)


if __name__ == "__main__":
    asyncio.run(main())