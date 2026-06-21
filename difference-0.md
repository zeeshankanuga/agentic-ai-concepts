# Architecture Comparison: Agent Files in `/agent` Directory

**Organized by Complexity Level: Lowest → Highest**

---

## Complexity Overview

| Level | File | Complexity | Lines of Code | Key Concept |
|-------|------|------------|---------------|-------------|
| **0** | `generative_ai.py` | **Lowest** | ~35 | Pure LLM Completion |
| **1** | `agent.py` | **Low** | ~55 | ReAct Agent (Direct Tools) |
| **1b** | `mcp_server.py` | **Low** | ~35 | MCP Server (FastMCP) |
| **2** | `agent_with_mcp.py` | **Medium** | ~45 | MCP Client Agent |
| **3** | `kubernetes-agent.py` | **Highest** | ~550 | Full Agentic System (LangGraph + RAG) |

---

## LEVEL 0: Pure LLM Completion — `generative_ai.py`

### Architecture Pattern
```
User Input → System Prompt + User Message → Ollama SDK → Response
```

### Code Structure
```python
import ollama

SYSTEM_PROMPT = "You are a Docker expert..."

while True:
    user_input = input("Enter your message:\n")
    if user_input == "exit": break
    
    response = ollama.chat(
        model="gemma4:e4b",
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_input}
        ]
    )
    print(response['message']['content'])
```

### Characteristics
| Aspect | Detail |
|--------|--------|
| **Agent Pattern** | None - pure chat completion |
| **Tool Integration** | NONE |
| **LLM Framework** | Ollama Python SDK (`ollama.chat()`) |
| **State Management** | None (stateless, no history) |
| **Execution Model** | Synchronous blocking loop |
| **Transport** | Direct Ollama API (HTTP/Unix socket) |
| **Dependencies** | `ollama` only |

### Pros / Cons
- ✅ Simplest possible implementation
- ✅ Minimal dependencies (1 package)
- ✅ Fastest response (no tool overhead)
- ❌ No tool use / action capability
- ❌ No memory / context persistence
- ❌ No reasoning loop
- ❌ Cannot interact with external systems

### When to Use
- Quick LLM chat, no tools needed
- Prototyping prompts
- Learning LLM basics

---

## LEVEL 1: ReAct Agent with Direct Tools — `agent.py`

### Architecture Pattern
```
User Input → LLM (with bound tools) → Tool Execution → Response
```

### Code Structure
```python
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import create_agent

@tool
def running_containers():
    """Show running Containers"""
    result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    return result.stdout

@tool
def container_logs_by_name(container_name):
    """Show Logs of Containers"""
    result = subprocess.run(["docker", "logs", "--tail", "10", container_name], capture_output=True, text=True)
    return result.stdout

llm = ChatOllama(model="gemma4:e4b", temperature="0.8", system=SYSTEM_PROMPT)
tools = [running_containers, container_logs_by_name]
agent = create_agent(llm, tools)

while True:
    user_input = input("Enter your message:\n")
    if user_input == "exit": break
    response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    print(response['messages'][-1].content)
```

### Characteristics
| Aspect | Detail |
|--------|--------|
| **Agent Pattern** | ReAct (Reasoning + Acting) |
| **Tool Integration** | Direct Python functions via `@tool` decorator |
| **LLM Framework** | LangChain + Ollama (`ChatOllama`) |
| **State Management** | None (stateless loop) |
| **Execution Model** | Synchronous `agent.invoke()` |
| **Transport** | Direct function calls (in-process) |
| **Dependencies** | `langchain`, `langchain-ollama`, `langchain-core` |

### Key Architecture Decisions
- Tools defined inline in same file as agent
- `@tool` decorator auto-generates JSON schema for LLM
- `create_agent()` handles ReAct loop internally
- Tools use `subprocess` to call Docker CLI

### Pros / Cons
- ✅ Simple, minimal dependencies for an agent
- ✅ Easy to understand and debug
- ✅ Tools execute in same process (fast)
- ❌ No separation of concerns (tools + agent coupled)
- ❌ No async support
- ❌ No retrieval/knowledge augmentation (no RAG)
- ❌ Tools tightly coupled to agent (not reusable)

### When to Use
- Simple agent with 2-3 tools
- Same process, same language
- Learning ReAct pattern basics

---

## LEVEL 1b: MCP Server (Tool Provider) — `mcp_server.py`

### Architecture Pattern
```
MCP Client ◀── stdio/JSON-RPC ──▶ FastMCP Server → Tools
```

### Code Structure
```python
from fastmcp import FastMCP
import subprocess

mcp = FastMCP("Docker MCP Server")

@mcp.tool
def running_containers():
    """Show running Containers"""
    result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    return result.stdout

@mcp.tool
def container_logs_by_name(container_name):
    """Show Logs of Containers"""
    result = subprocess.run(["docker", "logs", "--tail", "10", container_name], capture_output=True, text=True)
    return result.stdout

if __name__ == "__main__":
    mcp.run()
```

### Characteristics
| Aspect | Detail |
|--------|--------|
| **Role** | MCP Server (tool provider) |
| **Framework** | FastMCP (high-level MCP framework) |
| **Tool Definition** | `@mcp.tool` decorator (auto-generates schema) |
| **Transport** | stdio (JSON-RPC 2.0) |
| **Tools** | 2 Docker CLI wrappers |
| **Dependencies** | `fastmcp` |

### Key Architecture Decisions
- FastMCP handles JSON-RPC protocol internally
- Auto-generates tool schemas from function signatures
- `mcp.run()` manages stdio loop
- Same Docker CLI tools as `agent.py` but exposed via protocol

### Pros / Cons
- ✅ Simplest MCP server implementation
- ✅ Auto-generates tool schemas
- ✅ Protocol compliant (MCP standard)
- ✅ Tools reusable by any MCP client
- ❌ No custom protocol handling (less control)
- ❌ Tools still use subprocess (not API)
- ❌ No authentication/authorization built-in

### When to Use
- Building MCP server for others to consume
- Exposing existing functions as MCP tools
- Tool separation from agent logic

---

## LEVEL 2: MCP Client Agent — `agent_with_mcp.py`

### Architecture Pattern
```
┌──────────────────┐     stdio/JSON-RPC      ┌──────────────────┐
│  agent_with_mcp  │ ─────────────────────▶  │   mcp_server.py  │
│   (MCP Client)   │ ◀─────────────────────  │   (MCP Server)   │
└──────────────────┘                         └──────────────────┘
```

### Code Structure
```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
import asyncio

async def main():
    client = MultiServerMCPClient({
        "docker-mcp": {
            "transport": "stdio",
            "command": "python3",
            "args": ["mcp_server.py"]
        }
    })
    tools = await client.get_tools()  # Discover tools from MCP server

    llm = ChatOllama(model="gemma4:e4b", temperature="0.8")
    agent = create_agent(llm, tools)

    response = await agent.ainvoke({
        "messages": [{"role": "user", "content": "how many containers are running"}]
    })
    print(response['messages'][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
```

### Characteristics
| Aspect | Detail |
|--------|--------|
| **Agent Pattern** | ReAct (MCP-enabled) |
| **Tool Integration** | `MultiServerMCPClient` discovers tools at runtime |
| **LLM Framework** | LangChain + Ollama |
| **State Management** | None (single request/response) |
| **Execution Model** | Async (`asyncio.run`, `agent.ainvoke()`) |
| **Transport** | stdio subprocess + JSON-RPC 2.0 |
| **Dependencies** | `langchain`, `langchain-ollama`, `langchain-mcp-adapters` |

### Key Architecture Decisions
- Tools discovered dynamically from MCP server at startup
- Agent unchanged - just receives tools from MCP instead of local
- Async execution for MCP communication
- Separation of concerns: agent ≠ tools

### Pros / Cons
- ✅ Separation of concerns (agent ≠ tools)
- ✅ Protocol standardization (MCP)
- ✅ Tools can be written in any language
- ✅ Async support
- ❌ Still no persistent state or memory
- ❌ No RAG/knowledge retrieval
- ❌ Single-turn interaction only
- ❌ Requires running MCP server as subprocess

### When to Use
- Need tool separation / multi-language tools
- Multiple agents sharing same tool server
- Learning MCP client pattern

---

## LEVEL 3: Full Agentic AI System — `kubernetes-agent.py`

### Architecture Pattern
```
┌────────────────────────────────────────────────────────────────────────────┐
│                        kubernetes-agent.py (550+ lines)                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ rewrite_ │───▶│ retrieve │───▶│ decide_  │───▶│ execute_ │             │
│  │  query   │    │  (RAG)   │    │ action   │    │  tools   │             │
│  └──────────┘    └──────────┘    └────┬─────┘    └────┬─────┘             │
│                                       │             │                    │
│                                       ▼             ▼                    │
│                                ┌──────────┐    ┌──────────┐             │
│                                │ synthesize│◀───│  (loop)  │             │
│                                └──────────┘    └──────────┘             │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      SHARED STATE (AgentState)                     │  │
│  │  user_query, rewritten_query, retrieved_docs, tool_calls,         │  │
│  │  tool_results, final_answer, error                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  KnowledgeBase  │  │ KubernetesTools │  │       MCP Server        │  │
│  │  (ChromaDB +    │  │  (3 K8s tools)  │  │  (JSON-RPC over stdio)  │  │
│  │   Embeddings)   │  │                 │  │                         │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

### Code Structure (Key Components)

#### 1. State Definition (TypedDict)
```python
class AgentState(TypedDict):
    user_query: str
    rewritten_query: str
    retrieved_docs: List[str]
    tool_calls: List[Dict]
    tool_results: List[Dict]
    final_answer: str
    error: Optional[str]
```

#### 2. Knowledge Base (RAG Pipeline)
```python
class KnowledgeBase:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        self.vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=self.embeddings)
    
    def add_knowledge(self, documents): ...  # Chunk → Embed → Store
    def search(self, query, k=3): ...        # Embed → Similarity Search → Return
```

#### 3. Kubernetes Tools (API-based, not CLI)
```python
class KubernetesTools:
    def __init__(self, k8s: KubernetesManager):
        self.k8s = k8s
    
    def list_pods(self, namespace="default"): ...      # K8s API call
    def get_pod_logs(self, pod_name, namespace="default"): ...
    def analyze_pod(self, pod_name, namespace="default"): ...  # Issue detection
```

#### 4. LangGraph Workflow (5 Nodes)
```python
def build_agent_graph(k8s_tools, knowledge_base, llm):
    workflow = StateGraph(AgentState)
    
    workflow.add_node("rewrite_query", rewrite_query)      # Optimize query
    workflow.add_node("retrieve", retrieve)                # RAG search
    workflow.add_node("decide_action", decide_action)      # LLM decides: tool or answer
    workflow.add_node("execute_tools", execute_tools)      # Run K8s tools
    workflow.add_node("synthesize", synthesize)            # Combine results → answer
    
    # Flow: rewrite → retrieve → decide → (execute_tools → synthesize) OR synthesize
    workflow.add_conditional_edges("decide_action", route_after_decide)
    return workflow.compile()
```

#### 5. Custom MCP Server
```python
class MCPServer:
    def handle_request(self, request):  # JSON-RPC 2.0 handler
        if method == "tools/call":
            # Run agent graph with tool call as user query
            final_state = self.agent.invoke(initial_state)
            return {"result": {"content": [{"type": "text", "text": answer}]}}
```

#### 6. Multi-Provider LLM Factory
```python
def create_llm():
    if OLLAMA_AVAILABLE: return ChatOllama(model="llama3.1", temperature=0)
    if OPENAI_AVAILABLE: return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return MockLLM()  # Fallback for testing
```

### Characteristics
| Aspect | Detail |
|--------|--------|
| **Agent Pattern** | LangGraph Multi-Node Workflow |
| **Tool Integration** | Direct (K8s API) + MCP Server |
| **LLM Framework** | LangGraph + Multi-LLM (Ollama/OpenAI/Mock) |
| **State Management** | TypedDict (AgentState) - explicit, typed, persistent |
| **Execution Model** | Mixed (sync graph + async MCP) |
| **Knowledge** | RAG (ChromaDB + MiniLM embeddings) |
| **K8s Access** | Official `kubernetes` Python client (API calls) |
| **Dependencies** | 10+ packages (see below) |

### Dependencies
```txt
langchain, langgraph, langchain-ollama,
langchain-chroma, langchain-huggingface,
chromadb, sentence-transformers,
kubernetes, (optional: langchain-openai)
```

### Key Architecture Decisions

| Decision | Implementation |
|----------|----------------|
| **Workflow Orchestration** | LangGraph StateGraph with 5 explicit nodes |
| **State Management** | TypedDict shared across all nodes |
| **RAG Pipeline** | MiniLM embeddings → ChromaDB → RecursiveCharacterTextSplitter |
| **K8s Integration** | Official Python client (not CLI subprocess) |
| **Tool Design** | Class-based tools with issue detection logic |
| **LLM Flexibility** | Factory pattern with fallback chain |
| **MCP Server** | Custom JSON-RPC 2.0 implementation |
| **Observability** | Structured logging throughout |

### Pros / Cons
- ✅ Full agentic loop: reasoning → action → reflection
- ✅ RAG for knowledge augmentation
- ✅ Explicit state management (LangGraph)
- ✅ Separation of concerns (KB, Tools, Graph, MCP)
- ✅ Production patterns (error handling, logging, fallbacks)
- ✅ Educational comments explaining each concept
- ❌ High complexity - steep learning curve
- ❌ Many dependencies (10+ packages)
- ❌ Requires running Kubernetes cluster
- ❌ Not production-hardened (no auth, limited observability)

### When to Use
- Learning agentic AI concepts (RAG, Graph, State, MCP)
- Building Kubernetes troubleshooting agents
- Reference architecture for production systems
- Understanding how components compose

---

## Complexity Progression Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLEXITY EVOLUTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL 0: generative_ai.py                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LLM Only                                                           │   │
│  │  Input → [System Prompt + User] → Ollama → Output                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  LEVEL 1: agent.py                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ReAct Agent                                                        │   │
│  │  Input → LLM+Tools → Tool Exec → Output                            │   │
│  │  (Tools: inline @tool decorators, subprocess CLI)                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                   │                                    │
│                    ▼                   ▼                                    │
│  LEVEL 1b:      LEVEL 2:                                                │
│  mcp_server.py  agent_with_mcp.py                                       │
│  ┌─────────┐    ┌─────────────────────────────────────────────────────┐  │
│  │ MCP     │    │ MCP Client Agent                                    │  │
│  │ Server  │    │ Input → Discover Tools → LLM+Tools → Tool Exec → Out│  │
│  │         │    │ (Tools: external MCP server, JSON-RPC, async)       │  │
│  └─────────┘    └─────────────────────────────────────────────────────┘  │
│                    │                                                     │
│                    ▼                                                     │
│  LEVEL 3: kubernetes-agent.py                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Full Agentic System                                                 │  │
│  │ ┌──────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐ │  │
│  │ │Rewrite│→│Retrieve│→│ Decide │→│ Execute│→│Synthesize│→│  State   │ │  │
│  │ │ Query │  │ (RAG)  │  │ Action │  │ Tools  │  │ Answer   │  │ (TypedDict)│ │
│  │ └──────┘ └──────┘ └────────┘ └────────┘ └────────┘ └────────────┘ │  │
│  │      │         │          │           │          │                 │  │
│  │      ▼         ▼          ▼           ▼          ▼                 │  │
│  │ ┌──────────────────────────────────────────────────────────────┐   │  │
│  │ │  KnowledgeBase (ChromaDB)  │  KubernetesTools (API)         │   │  │
│  │ │  MCP Server (JSON-RPC)     │  Multi-LLM (Ollama/OpenAI)     │   │  │
│  │ └──────────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Comparison Matrix by Complexity Level

| Feature | L0: generative_ai.py | L1: agent.py | L1b: mcp_server.py | L2: agent_with_mcp.py | L3: kubernetes-agent.py |
|---------|---------------------|--------------|-------------------|----------------------|------------------------|
| **Lines of Code** | ~35 | ~55 | ~35 | ~45 | ~550 |
| **Agent Pattern** | None | ReAct | N/A (Server) | ReAct (MCP) | LangGraph Multi-Node |
| **Tools** | None | 2 (inline) | 2 (exposed) | 2 (discovered) | 3 (K8s API) + MCP |
| **Tool Protocol** | N/A | Direct Python | MCP (FastMCP) | MCP (JSON-RPC) | Direct + MCP |
| **State** | None | None | None | None | TypedDict (LangGraph) |
| **Memory** | No | No | No | No | Conversation + RAG |
| **Knowledge** | System Prompt | System Prompt | No | System Prompt | Vector DB (Chroma) |
| **RAG** | No | No | No | No | Yes (MiniLM + Chroma) |
| **Async** | No | No | No | Yes | Mixed |
| **K8s Access** | No | Docker CLI | Docker CLI | Docker CLI (via MCP) | K8s Python Client |
| **LLM Providers** | Ollama only | Ollama only | N/A | Ollama only | Ollama + OpenAI + Mock |
| **Extensibility** | None | Low | Medium | Medium (MCP) | High |
| **Dependencies** | 1 | 3 | 1 | 3 | 10+ |

---

## Learning Path Recommendation

### For Beginners (Start Here)
1. **`generative_ai.py`** — Understand LLM completion basics
2. **`agent.py`** — Learn ReAct pattern with direct tools
3. **`mcp_server.py`** — Learn MCP server basics

### For Intermediate (MCP & Protocol)
4. **`agent_with_mcp.py`** — Learn MCP client pattern
5. Run both `mcp_server.py` and `agent_with_mcp.py` together

### For Advanced (Full System)
6. **`kubernetes-agent.py`** — Study complete agentic architecture
   - LangGraph workflow orchestration
   - RAG implementation
   - Typed state management
   - Multi-component integration

---

## File Dependencies Summary

```txt
generative_ai.py (L0)
    └── ollama

agent.py (L1)
    └── langchain, langchain-ollama, langchain-core

mcp_server.py (L1b)
    └── fastmcp

agent_with_mcp.py (L2)
    └── langchain, langchain-ollama, langchain-mcp-adapters
    └── requires: mcp_server.py running

kubernetes-agent.py (L3)
    ├── langchain, langgraph, langchain-ollama
    ├── langchain-chroma, langchain-huggingface
    ├── chromadb, sentence-transformers
    ├── kubernetes
    └── (optional) langchain-openai
    └── includes: own MCP Server implementation
```

---

## Conclusion

These 5 files form a **complete learning progression** from basic LLM usage to a production-pattern agentic system:

| Level | File | Purpose |
|-------|------|---------|
| **0** | `generative_ai.py` | Foundation: LLM as completion engine |
| **1** | `agent.py` | Step 1: Add tools via direct binding (ReAct) |
| **1b** | `mcp_server.py` | Step 1b: Extract tools to MCP server |
| **2** | `agent_with_mcp.py` | Step 2: Consume MCP tools (protocol-based) |
| **3** | `kubernetes-agent.py` | Step 3: Full system with state, RAG, workflow, production patterns |

**Study in order** for maximum learning value. Each level adds one architectural concept:
- L0→L1: Tools + Reasoning loop
- L1→L1b: Protocol separation (MCP)
- L1b→L2: Protocol consumption
- L2→L3: State + RAG + Workflow + Multi-component architecture