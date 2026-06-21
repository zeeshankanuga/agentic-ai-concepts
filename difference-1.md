# Agentic AI Concepts - File Comparison

This document provides a comprehensive comparison of all 10 Python files in the agentic-ai-concepts project, showing the evolution from basic LLM usage to a full Kubernetes agent with RAG, LangGraph, and MCP.

---

## File Overview

| File | Level | Pattern | Key Concepts |
|------|-------|---------|--------------|
| 01-generative_ai.py | 1 | Basic LLM | Direct Ollama chat, system prompt, no tools |
| 02-agent.py | 2 | LangChain Agent | Tools as functions, `create_agent`, Docker CLI |
| 03-mcp_server.py | 3 | MCP Server | FastMCP, stdio transport, tool definitions |
| 04-agent_with_mcp.py | 4 | MCP Client | `MultiServerMCPClient`, async, MCP tools |
| 05a-agent-with-memory.py | 5a | Conversation Memory | Message history, context window management |
| 05b-async-agent.py | 5b | Async Patterns | Streaming, concurrent execution, context managers |
| 05c-agent-with-rag.py | 5c | RAG (In-Memory) | Chunking, embeddings simulation, retrieval |
| 05d-langgraph-basics.py | 5d | LangGraph Workflow | StateGraph, nodes, conditional edges |
| 05e-class-based-tools.py | 5e | Structured Tools | Class-based tools, typed results, analysis tools |
| 05f-multi-step-agent.py | 5f | Multi-Step Reasoning | Plan→Execute→Reflect→Synthesize loop |
| 06-kubernetes-agent.py | 6 | Full System | K8s API, ChromaDB, LangGraph, MCP server |

---

## Detailed Comparison by Concept

### 1. LLM Integration

| File | LLM Library | Model | Temperature | System Prompt |
|------|-------------|-------|-------------|---------------|
| 01-generative_ai.py | `ollama` (native) | gemma4:e4b | Default | Inline string |
| 02-agent.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0.8 | Inline string |
| 03-mcp_server.py | N/A (server only) | - | - | - |
| 04-agent_with_mcp.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0.8 | Not set (passed via MCP) |
| 05a-agent-with-memory.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0.8 | Inline constant |
| 05b-async-agent.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0.8 | Inline constant + callbacks |
| 05c-agent-with-rag.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0.8 | Inline constant |
| 05d-langgraph-basics.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0 | Inline constant |
| 05e-class-based-tools.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0 | Inline constant |
| 05f-multi-step-agent.py | `langchain_ollama.ChatOllama` | gemma4:e4b | 0 | Inline constant |
| 06-kubernetes-agent.py | `langchain_ollama.ChatOllama` or `ChatOpenAI` | llama3.1 / gpt-4o-mini | 0 | Built into prompts |

**Evolution**: Native Ollama → LangChain wrapper → Multiple LLM support with fallback (Ollama → OpenAI → Mock)

---

### 2. Tool Patterns

| File | Tool Definition | Tool Count | Tool Type |
|------|-----------------|------------|-----------|
| 01-generative_ai.py | None | 0 | - |
| 02-agent.py | `@tool` decorator | 2 | Sync functions |
| 03-mcp_server.py | `@mcp.tool` decorator | 2 | FastMCP tools |
| 04-agent_with_mcp.py | MCP client discovery | Dynamic | MCP stdio |
| 05a-agent-with-memory.py | MCP client discovery | Dynamic | MCP stdio |
| 05b-async-agent.py | MCP client discovery | Dynamic | MCP stdio |
| 05c-agent-with-rag.py | MCP + `@tool` for RAG | 3+ | Hybrid |
| 05d-langgraph-basics.py | `@tool` + subprocess | 2 | Sync functions |
| 05e-class-based-tools.py | Class-based (`BaseTool`) | 6 | Structured classes |
| 05f-multi-step-agent.py | `@tool` decorator | 3 | Sync functions |
| 06-kubernetes-agent.py | Class methods + `@tool` | 3 | K8s API calls |

**Key Evolution**:
- **Level 2**: Simple `@tool` functions returning strings
- **Level 3**: MCP protocol tools (JSON-RPC over stdio)
- **Level 4-5b**: MCP client discovers tools dynamically
- **Level 5c**: Hybrid - MCP tools + RAG search tool
- **Level 5d**: Tools called via LangGraph nodes
- **Level 5e**: Class-based with `ToolResult` typed output, dependency injection
- **Level 5f**: Tools integrated into reasoning steps
- **Level 6**: Kubernetes API client tools with structured output

---

### 3. Memory & Conversation

| File | Memory Type | Context Management | Persistence |
|------|-------------|-------------------|-------------|
| 01-generative_ai.py | None | Single request | None |
| 02-agent.py | None | Single request | None |
| 03-mcp_server.py | N/A | N/A | N/A |
| 04-agent_with_mcp.py | None | Single request | None |
| **05a-agent-with-memory.py** | **Message list** | **Sliding window (20 msgs)** | **In-memory only** |
| 05b-async-agent.py | Message list + metrics | Sliding window (20 msgs) | In-memory |
| 05c-agent-with-rag.py | Message list + KB | Sliding window (20 msgs) | In-memory KB |
| 05d-langgraph-basics.py | StateGraph (TypedDict) | Per-invocation | Graph state |
| 05e-class-based-tools.py | Message list | Standard | In-memory |
| 05f-multi-step-agent.py | Reasoning trace + plan | Explicit steps | In-memory |
| 06-kubernetes-agent.py | LangGraph State | Per-invocation | ChromaDB (vector) |

**New in 05a**: `SystemMessage`, `HumanMessage`, `AIMessage` with context trimming
**New in 05b**: `AgentMetrics` dataclass tracking requests, tokens, tools, errors
**New in 05d**: `AgentState` TypedDict shared across graph nodes
**New in 05f**: `ReasoningStep` trace with `StepType` enum (PLAN, THINK, ACT, OBSERVE, REFLECT, SYNTHESIZE)

---

### 4. Async Patterns

| File | Async Support | Streaming | Concurrency | Context Manager |
|------|---------------|-----------|-------------|-----------------|
| 01-generative_ai.py | ❌ | ❌ | ❌ | ❌ |
| 02-agent.py | ❌ | ❌ | ❌ | ❌ |
| 03-mcp_server.py | ❌ (sync) | ❌ | ❌ | ❌ |
| 04-agent_with_mcp.py | ✅ `asyncio.run` | ❌ | ❌ | ❌ |
| 05a-agent-with-memory.py | ✅ `async/await` | ❌ | ❌ | ❌ |
| **05b-async-agent.py** | ✅ **Full async** | ✅ **Token streaming** | ✅ **asyncio.gather** | ✅ **`__aenter__`/`__aexit__`** |
| 05c-agent-with-rag.py | ✅ `async/await` | ❌ | ❌ | ❌ |
| 05d-langgraph-basics.py | ✅ `graph.invoke` | ❌ | ❌ | ❌ |
| 05e-class-based-tools.py | ✅ `async/await` | ❌ | ❌ | ❌ |
| 05f-multi-step-agent.py | ✅ `async/await` | ❌ | ❌ | ❌ |
| 06-kubernetes-agent.py | ✅ `async` available | ❌ | ❌ | ❌ |

**05b Highlights**:
- `StreamingCallbackHandler` with `on_llm_new_token`
- `run_concurrent_queries()` using `asyncio.gather`
- `AsyncDockerAgent` with `__aenter__`/`__aexit__` for resource cleanup
- Background tasks with `asyncio.create_task`
- `@asynccontextmanager` for quick scripts

---

### 5. RAG (Retrieval-Augmented Generation)

| File | RAG Type | Chunking | Embeddings | Vector Store | Retrieval |
|------|----------|----------|------------|--------------|-----------|
| 01-05b | None | - | - | - | - |
| **05c-agent-with-rag.py** | **In-memory (simulated)** | ✅ `SimpleTextSplitter` | ✅ **TF-IDF simulator** | Dict-based | Keyword scoring |
| 05d-langgraph-basics.py | Keyword dict | ❌ | ❌ | Dict | Keyword match |
| 05e-class-based-tools.py | None | - | - | - | - |
| 05f-multi-step-agent.py | None | - | - | - | - |
| **06-kubernetes-agent.py** | **Production (ChromaDB)** | ✅ `RecursiveCharacterTextSplitter` | ✅ **MiniLM-L6-v2** | **ChromaDB** | **Similarity search** |

**05c Implementation Details**:
- `SimpleTextSplitter`: 500 char chunks, 50 char overlap, sentence-boundary aware
- `SimpleEmbeddingSimulator`: TF-IDF style keyword overlap scoring
- `InMemoryKnowledgeBase`: Document ingestion, chunking, indexing, retrieval
- `RetrievalResult`: Document, chunk, score, chunk_index
- `get_context_for_prompt()`: Formats retrieved knowledge for LLM

**06 Implementation Details**:
- `HuggingFaceEmbeddings` with `sentence-transformers/all-MiniLM-L6-v2` (384 dim)
- `RecursiveCharacterTextSplitter`: 500 chunk_size, 50 overlap
- `Chroma` with persist_directory, collection_name
- `similarity_search_with_score()` returns (doc, score) tuples

---

### 6. LangGraph Workflow

| File | Graph Type | Nodes | Edges | Conditional Edges | State |
|------|------------|-------|-------|-------------------|-------|
| 01-05c | None | - | - | - | - |
| **05d-langgraph-basics.py** | **StateGraph** | **5** | **4** | **1** | **TypedDict** |
| 05e-class-based-tools.py | None | - | - | - | - |
| 05f-multi-step-agent.py | Manual loop | - | - | - | Dataclass |
| **06-kubernetes-agent.py** | **StateGraph** | **5** | **4** | **1** | **TypedDict** |

**05d Node Flow**:
```
rewrite_query → retrieve → decide_action → (execute_tools →) synthesize
                      ↑                           │
                      └───────────────────────────┘ (conditional)
```

**05d State (AgentState)**:
```python
class AgentState(TypedDict):
    user_query: str
    rewritten_query: str
    retrieved_context: str
    tool_calls: List[Dict]
    tool_results: List[Dict]
    final_answer: str
    error: Optional[str]
    step: str
```

**06 Node Flow** (same pattern, K8s-specific):
```
rewrite_query → retrieve → decide_action → (execute_tools →) synthesize
```

---

### 7. Multi-Step Reasoning (05f Unique)

| Component | Description |
|-----------|-------------|
| `StepType` enum | PLAN, THINK, ACT, OBSERVE, REFLECT, SYNTHESIZE |
| `ReasoningStep` | Step number, type, content, tool info, confidence |
| `AgentPlan` | Goal, steps list, current_step, completed_steps |
| `plan()` | LLM creates JSON plan from query |
| `execute_step()` | Think → Act/Reason → Observe |
| `reflect()` | LLM evaluates progress, can add steps |
| `synthesize()` | Final answer from full trace |

**Reasoning Loop**:
```
Plan (create steps) → 
  For each step: Think → Act (tool) → Observe → Reflect (continue?) →
Synthesize
```

---

### 8. Class-Based Tools (05e Unique)

| Class | Purpose |
|-------|---------|
| `ToolStatus` enum | SUCCESS, ERROR, PARTIAL |
| `ToolResult` dataclass | status, data, error, metadata + factory methods |
| `BaseTool` (ABC) | name, description, input_schema, execute(), to_langchain_tool(), to_mcp_tool() |
| `DockerToolSet` | Dependency injection, shared Docker client, tool registry |
| `ListContainersTool` | Structured output (JSON/table), error handling |
| `GetContainerLogsTool` | Tail, since, follow params |
| `InspectContainerTool` | Go template format support |
| `GetContainerStatsTool` | Resource usage parsing |
| `AnalysisToolSet` | **Logic inside tools**: `analyze_container_health()`, `diagnose_common_issues()` |

**Key Innovation**: Tools return `ToolResult` (structured) not raw strings. Analysis tools embed domain logic (health checks, restart detection, resource limit validation) that would otherwise require LLM reasoning.

---

### 9. Kubernetes Integration (06 Unique)

| Component | Library | Purpose |
|-----------|---------|---------|
| `KubernetesManager` | `kubernetes.client` | In-cluster + kubeconfig, CoreV1Api |
| `KnowledgeBase` | `langchain_chroma`, `sentence-transformers` | Vector DB with MiniLM embeddings |
| `KubernetesTools` | K8s API | list_pods, get_pod_logs, analyze_pod |
| `MCPServer` | JSON-RPC stdio | tools/list, tools/call, initialize |
| `build_agent_graph()` | `langgraph` | 5-node workflow |

**K8s Tools**:
1. `list_pods(namespace)` → name, status, restarts, node, age
2. `get_pod_logs(pod_name, namespace, tail_lines)` → recent logs
3. `analyze_pod(pod_name, namespace)` → detects CrashLoopBackOff, OOMKilled, high restarts

**Knowledge Base Topics**:
- Pod lifecycle phases
- Common issues (CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending)
- Debugging commands (kubectl describe, logs, top, events)
- Resource management (requests/limits, QoS classes)

---

### 10. MCP (Model Context Protocol)

| File | Role | Transport | Tool Discovery |
|------|------|-----------|----------------|
| 03-mcp_server.py | **Server** | stdio | `@mcp.tool` decorator |
| 04-agent_with_mcp.py | **Client** | stdio | `MultiServerMCPClient` |
| 05a-agent-with-memory.py | Client | stdio | `MultiServerMCPClient` |
| 05b-async-agent.py | Client | stdio | `MultiServerMCPClient` |
| 05c-agent-with-rag.py | Client | stdio | `MultiServerMCPClient` |
| 06-kubernetes-agent.py | **Server** | stdio | `MCPServer` class + JSON-RPC |

**03 Server**: FastMCP with 2 tools, `mcp.run()` blocks on stdio
**04-05c Client**: `MultiServerMCPClient` with `"transport": "stdio"`, `"command": "python3"`, `"args": ["03-mcp_server.py"]`
**06 Server**: Custom `MCPServer` class handling `initialize`, `tools/list`, `tools/call` JSON-RPC methods

---

### 11. Error Handling

| File | Try/Except | Structured Errors | Retry Logic | Logging |
|------|------------|-------------------|-------------|---------|
| 01-generative_ai.py | ❌ | ❌ | ❌ | print() |
| 02-agent.py | ❌ | ❌ | ❌ | print() |
| 03-mcp_server.py | ❌ | ❌ | ❌ | - |
| 04-agent_with_mcp.py | ❌ | ❌ | ❌ | - |
| 05a-agent-with-memory.py | ✅ | ❌ | ❌ | print() |
| 05b-async-agent.py | ✅ | ✅ (metrics.errors) | ❌ | print() |
| 05c-agent-with-rag.py | ✅ | ❌ | ❌ | print() |
| 05d-langgraph-basics.py | ✅ | State.error field | ❌ | print() |
| 05e-class-based-tools.py | ✅ | **ToolResult.error()** | ❌ | - |
| 05f-multi-step-agent.py | ✅ | Tool result error field | ❌ | print() |
| 06-kubernetes-agent.py | ✅ | Tool result error field | ❌ | **logging module** |

**05e Best Practice**: `ToolResult.error()`, `ToolResult.success()`, `ToolResult.partial()` factory methods with consistent dict output via `to_dict()`.

---

### 12. Configuration & Extensibility

| File | Config Method | Extensibility |
|------|---------------|---------------|
| 01-generative_ai.py | Hardcoded | None |
| 02-agent.py | Hardcoded | Add @tool functions |
| 03-mcp_server.py | Hardcoded | Add @mcp.tool methods |
| 04-agent_with_mcp.py | Client config dict | Add MCP servers |
| 05a-agent-with-memory.py | Constants | MAX_MESSAGES |
| 05b-async-agent.py | **Constructor params** | Model, temp, background tasks |
| 05c-agent-with-rag.py | **Constructor params** | Chunk size, overlap, KB content |
| 05d-langgraph-basics.py | Function params | Graph nodes, knowledge dict |
| 05e-class-based-tools.py | **Constructor DI** | Tool classes, DockerToolSet |
| 05f-multi-step-agent.py | Constructor params | max_steps, tools dict |
| 06-kubernetes-agent.py | **Env vars + constructor** | K8s config, LLM choice, KB docs |

---

## Architecture Evolution Summary

```
Level 1: 01-generative_ai.py
    │
    ├─► Basic LLM chat loop
    └─► No tools, no memory, sync

Level 2: 02-agent.py
    │
    ├─► LangChain Agent + @tool
    ├─► Docker CLI via subprocess
    └─► Still sync, no memory

Level 3: 03-mcp_server.py
    │
    ├─► MCP Server (FastMCP)
    ├─► Tools exposed via JSON-RPC
    └─► Stdio transport

Level 4: 04-agent_with_mcp.py
    │
    ├─► MCP Client (MultiServerMCPClient)
    ├─► Dynamic tool discovery
    └─► Async invocation

Level 5a: 05a-agent-with-memory.py
    │
    ├─► Conversation history (messages list)
    ├─► Context window management
    └─► Clear/exit commands

Level 5b: 05b-async-agent.py
    │
    ├─► Full async architecture
    ├─► Token streaming (callbacks)
    ├─► Concurrent queries (asyncio.gather)
    ├─► Context managers (__aenter__/__aexit__)
    ├─► Background tasks
    └─► Metrics tracking

Level 5c: 05c-agent-with-rag.py
    │
    ├─► In-memory RAG (no external deps)
    ├─► Text chunking (SimpleTextSplitter)
    ├─► TF-IDF embedding simulation
    ├─► Knowledge base with retrieval
    └─► Source attribution

Level 5d: 05d-langgraph-basics.py
    │
    ├─► LangGraph StateGraph
    ├─► TypedDict state
    ├─► 5 nodes with conditional routing
    └─► Explicit workflow orchestration

Level 5e: 05e-class-based-tools.py
    │
    ├─► Class-based tool architecture
    ├─► Dependency injection (DockerToolSet)
    ├─► Structured ToolResult (typed)
    ├─► Analysis tools (logic in tools)
    ├─► JSON Schema generation
    └─► LangChain + MCP conversion

Level 5f: 05f-multi-step-agent.py
    │
    ├─► Explicit multi-step reasoning
    ├─► Plan → Execute → Reflect → Synthesize
    ├─► Visible reasoning trace
    ├─► Self-correction (reflection adds steps)
    └─► Step types: PLAN/THINK/ACT/OBSERVE/REFLECT/SYNTHESIZE

Level 6: 06-kubernetes-agent.py
    │
    ├─► Production K8s integration
    ├─► ChromaDB + MiniLM embeddings
    ├─► LangGraph workflow (5 nodes)
    ├─► MCP Server (JSON-RPC)
    ├─► Multiple LLM support (Ollama/OpenAI/Mock)
    └─► Kubernetes troubleshooting knowledge base
```

---

## Code Reuse Patterns

### Shared Across Files

| Pattern | Files |
|---------|-------|
| `SYSTEM_PROMPT` constant | 01, 02, 05a, 05b, 05c, 05d, 05e, 05f |
| `docker` CLI via subprocess | 02, 03, 05d, 05e |
| `while True` input loop | 01, 02, 05a, 05b, 05c, 05d, 05e, 05f |
| `exit` command handling | 01, 02, 05a, 05b, 05c, 05d, 05e, 05f |

### Unique to Each Level

| Level | Unique Feature |
|-------|----------------|
| 1 | Native Ollama `ollama.chat()` |
| 2 | `langchain.agents.create_agent` |
| 3 | `FastMCP` server |
| 4 | `MultiServerMCPClient` |
| 5a | `SystemMessage`/`HumanMessage`/`AIMessage` history |
| 5b | `StreamingCallbackHandler`, `asyncio.gather`, `__aenter__` |
| 5c | `SimpleTextSplitter`, `SimpleEmbeddingSimulator`, `InMemoryKnowledgeBase` |
| 5d | `StateGraph`, `TypedDict`, conditional edges |
| 5e | `BaseTool` ABC, `ToolResult`, `DockerToolSet`, `AnalysisToolSet` |
| 5f | `StepType`, `ReasoningStep`, `AgentPlan`, reflection loop |
| 6 | `KubernetesManager`, `Chroma`, `HuggingFaceEmbeddings`, `MCPServer` |

---

## Dependencies by File

| File | Core Deps | Optional/Dev Deps |
|------|-----------|-------------------|
| 01-generative_ai.py | `ollama` | - |
| 02-agent.py | `langchain-ollama`, `langchain-core`, `langchain` | - |
| 03-mcp_server.py | `fastmcp` | - |
| 04-agent_with_mcp.py | `langchain-mcp-adapters`, `langchain-ollama`, `langchain` | - |
| 05a-agent-with-memory.py | `langchain-mcp-adapters`, `langchain-ollama`, `langchain-core`, `langchain` | - |
| 05b-async-agent.py | Same as 5a | - |
| 05c-agent-with-rag.py | Same as 5a | - |
| 05d-langgraph-basics.py | `langgraph`, `langchain-ollama`, `langchain-core` | - |
| 05e-class-based-tools.py | `langchain-ollama`, `langchain-core`, `langchain` | - |
| 05f-multi-step-agent.py | `langchain-ollama`, `langchain-core` | - |
| 06-kubernetes-agent.py | `kubernetes`, `langchain`, `langgraph`, `langchain-chroma`, `langchain-huggingface`, `langchain-text-splitters`, `sentence-transformers`, `chromadb` | `langchain-ollama`, `langchain-openai` |

---

## Running Each File

```bash
# Level 1: Basic chat
python3 01-generative_ai.py

# Level 2: LangChain agent (needs Docker)
python3 02-agent.py

# Level 3: MCP Server (run in separate terminal)
python3 03-mcp_server.py

# Level 4: MCP Client (needs Level 3 running)
python3 04-agent_with_mcp.py

# Level 5a: Agent with memory
python3 05a-agent-with-memory.py

# Level 5b: Async agent with streaming
python3 05b-async-agent.py
python3 05b-async-agent.py --demo  # Demo concurrent queries

# Level 5c: RAG agent
python3 05c-agent-with-rag.py
python3 05c-agent-with-rag.py --demo  # Demo retrieval only

# Level 5d: LangGraph agent
python3 05d-langgraph-basics.py
python3 05d-langgraph-basics.py --demo  # Demo queries

# Level 5e: Structured tools
python3 05e-class-based-tools.py
python3 05e-class-based-tools.py --demo  # Demo tool outputs

# Level 5f: Multi-step reasoning
python3 05f-multi-step-agent.py
python3 05f-multi-step-agent.py --demo  # Demo with traces

# Level 6: Kubernetes agent (needs K8s cluster + deps)
pip install kubernetes langchain langgraph chromadb sentence-transformers langchain-chroma langchain-huggingface langchain-text-splitters
python3 06-kubernetes-agent.py
```

---

## Learning Path Recommendation

1. **Start with 01-02**: Understand basic LLM → Agent with tools
2. **Study 03-04**: Learn MCP client/server pattern
3. **Master 05a-05b**: Conversation memory + async patterns
4. **Explore 05c**: RAG concepts without heavy dependencies
5. **Understand 05d**: LangGraph workflow orchestration
6. **Learn 05e**: Production tool patterns (structured, class-based)
7. **Practice 05f**: Explicit reasoning traces
8. **Build on 06**: Full system integration

---

## Key Takeaways

| Concept | First Introduced | Production Pattern |
|---------|-----------------|-------------------|
| Tools | 02 (functions) | 05e (classes) |
| MCP | 03 (server), 04 (client) | 06 (custom server) |
| Memory | 05a (message list) | 05d/06 (LangGraph State) |
| Async | 04 (basic) | 05b (full patterns) |
| Streaming | 05b (callbacks) | - |
| Concurrency | 05b (asyncio.gather) | - |
| RAG | 05c (simulated) | 06 (ChromaDB + MiniLM) |
| LangGraph | 05d (5 nodes) | 06 (5 nodes, K8s) |
| Structured Output | 05e (ToolResult) | 06 (tool results) |
| Multi-step Reasoning | 05f (explicit) | - |
| K8s Integration | 06 (only) | 06 |
| Vector DB | 06 (ChromaDB) | 06 |
| Embeddings | 05c (simulated), 06 (MiniLM) | 06 |
| Logging | 06 (logging module) | 06 |

---

*Generated by comparing all 10 Python files in the agentic-ai-concepts project.*