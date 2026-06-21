# Agentic AI Concepts - Progressive Learning Differences

This document tracks the incremental evolution of concepts across all Python files in this directory. Each level builds upon the previous one, introducing new agentic AI patterns.

---

## File Overview & Progression

| Level | File | Lines | Key Concept Introduced |
|-------|------|-------|------------------------|
| 1 | `01-generative_ai.py` | ~25 | Basic LLM chat loop |
| 2 | `02-agent.py` | ~50 | Tools + Agent (LangChain) |
| 3 | `03-mcp_server.py` | ~35 | MCP Server (FastMCP) |
| 4 | `04-agent_with_mcp.py` | ~40 | Agent + MCP Client |
| 5a | `05a-agent-with-memory.py` | ~120 | Conversation Memory |
| 5b | `05b-async-agent.py` | ~280 | Async Patterns + Streaming |
| 5c | `05c-agent-with-rag.py` | ~380 | RAG (Retrieval-Augmented Generation) |
| 5d | `05d-langgraph-basics.py` | ~300 | LangGraph Workflow |
| 5e | `05e-class-based-tools.py` | ~350 | Class-Based Structured Tools |
| 5f | `05f-multi-step-agent.py` | ~320 | Multi-Step Reasoning |
| 6 | `06-kubernetes-agent.py` | ~500 | Full Production System |

---

## Level-by-Level Differences

### Level 1 → Level 2: Basic Chat → Tool-Using Agent

**01-generative_ai.py** (25 lines):
```python
# Simple loop: User input → LLM → Print response
response = ollama.chat(model="gemma4:e4b", messages=[system, user])
```

**02-agent.py** (50 lines) - **NEW**:
- `@tool` decorator for function calling
- `create_agent(llm, tools)` - LangChain agent creation
- Tools execute shell commands (`docker ps`, `docker logs`)
- Agent decides when to use tools automatically

**Key Difference**: LLM now has **agency** - it can take actions via tools.

---

### Level 2 → Level 3: Local Tools → MCP Server

**02-agent.py**: Tools defined inline, executed locally.

**03-mcp_server.py** (35 lines) - **NEW**:
- `FastMCP` server exposing tools via stdio
- `@mcp.tool` decorator (different from LangChain `@tool`)
- Tools run in separate process, communicate via JSON-RPC
- `mcp.run()` starts the server

**Key Difference**: Tools are now **remote/external** - accessible via standard protocol (MCP).

---

### Level 3 → Level 4: MCP Server → Agent Using MCP

**04-agent_with_mcp.py** (40 lines) - **NEW**:
- `MultiServerMCPClient` connects to MCP server
- `client.get_tools()` discovers tools dynamically
- Agent uses MCP tools exactly like local tools
- `asyncio.run(main())` for async MCP communication

**Key Difference**: Agent now **consumes external tools** via MCP protocol.

---

### Level 4 → Level 5a: Single Request → Conversation Memory

**04-agent_with_mcp.py**: Each `ainvoke` is independent - no memory.

**05a-agent-with-memory.py** (120 lines) - **NEW**:
- `messages` list maintains full conversation history
- `SystemMessage`, `HumanMessage`, `AIMessage` for roles
- Context window management (sliding window, max 20 messages)
- `clear` command to reset memory
- Explicit comments explaining each concept

**Key Difference**: Agent now has **persistent memory** across turns.

---

### Level 5a → Level 5b: Sync → Full Async Architecture

**05a-agent-with-memory.py**: Basic async with `ainvoke`.

**05b-async-agent.py** (280 lines) - **NEW**:
- `AsyncDockerAgent` class with `__aenter__`/`__aexit__` context manager
- `StreamingCallbackHandler` for token-by-token streaming
- `asyncio.gather` for **concurrent query execution**
- `AgentMetrics` dataclass for performance tracking
- Background tasks with `asyncio.create_task`
- `@asynccontextmanager` for resource management
- Concurrent demo: 3 queries in parallel vs sequential

**Key Difference**: Production-ready **async patterns**, streaming, and concurrency.

---

### Level 5b → Level 5c: Async Agent → RAG-Enabled Agent

**05b-async-agent.py**: Pure tool-based, no external knowledge.

**05c-agent-with-rag.py** (380 lines) - **NEW**:
- `InMemoryKnowledgeBase` - no external vector DB needed
- `SimpleTextSplitter` - chunking (500 chars, 50 overlap)
- `SimpleEmbeddingSimulator` - TF-IDF style keyword scoring
- `Document`, `RetrievalResult` dataclasses
- RAG flow: Query → Search → Augment Prompt → LLM
- Pre-loaded Docker knowledge (4 documents, 4 topics)
- `search` command to test retrieval independently
- Source attribution in responses

**Key Difference**: Agent now **retrieves knowledge** before generating (RAG).

---

### Level 5c → Level 5d: Linear Agent → LangGraph Workflow

**05c-agent-with-rag.py**: Single agent with internal RAG.

**05d-langgraph-basics.py** (300 lines) - **NEW**:
- `AgentState` TypedDict - shared memory across nodes
- 5 explicit nodes: `rewrite_query` → `retrieve` → `decide_action` → `execute_tools` → `synthesize`
- Conditional edges with `route_after_decide` (branching logic)
- `StateGraph` compilation and invocation
- Explicit state passing between nodes
- Each node is a pure function reading/writing state

**Key Difference**: **Graph-based orchestration** with explicit nodes and edges.

---

### Level 5d → Level 5e: Function Tools → Class-Based Structured Tools

**05d-langgraph-basics.py**: Tools as simple `@tool` functions returning strings.

**05e-class-based-tools.py** (350 lines) - **NEW**:
- `BaseTool` abstract class with `name`, `description`, `input_schema`
- `ToolResult` dataclass with `status`, `data`, `error`, `metadata`
- `DockerToolSet` class - dependency injection, shared Docker client
- 4 structured tools: `list_containers`, `get_container_logs`, `inspect_container`, `get_container_stats`
- `AnalysisToolSet` - tools with **built-in logic** (health analysis, issue diagnosis)
- Tools return structured JSON, not raw text
- `to_langchain_tool()` and `to_mcp_tool()` conversion methods

**Key Difference**: **Structured, typed tools** with domain logic inside tools.

---

### Level 5e → Level 5f: Single-Step → Multi-Step Reasoning

**05e-class-based-tools.py**: Agent decides tool use in one step.

**05f-multi-step-agent.py** (320 lines) - **NEW**:
- `StepType` enum: PLAN, THINK, ACT, OBSERVE, REFLECT, SYNTHESIZE
- `ReasoningStep` dataclass - visible trace of every step
- `AgentPlan` - explicit multi-step plan created upfront
- Plan-and-execute pattern: separate planning from execution
- Reflection loop after each step (can add steps dynamically)
- Full reasoning trace printed at end
- `trace` command to view reasoning

**Key Difference**: **Explicit multi-step reasoning** with visible trace and reflection.

---

### Level 5f → Level 6: Learning Demos → Production System

**05f-multi-step-agent.py**: Demo with 3 simple tools, mock LLM.

**06-kubernetes-agent.py** (500 lines) - **NEW**:
- Real Kubernetes client (`kubernetes` Python SDK)
- **ChromaDB** vector database with `sentence-transformers` embeddings
- `RecursiveCharacterTextSplitter` for proper chunking
- `HuggingFaceEmbeddings` (MiniLM-L6-v2, 384 dims)
- LangGraph with 5 nodes (same pattern as 5d but production-ready)
- MCP Server implementation (JSON-RPC over stdio)
- Real LLM support (Ollama + OpenAI fallback)
- 4 knowledge documents loaded into vector DB
- Kubernetes-specific tools: `list_pods`, `get_pod_logs`, `analyze_pod`
- In-cluster and kubeconfig authentication
- Comprehensive error handling and logging

**Key Difference**: **Production-ready** with real K8s, real vector DB, real embeddings, MCP server.

---

## Concept Evolution Summary

```
LEVEL 1:  LLM Chat              →  "Talk to me"
LEVEL 2:  + Tools               →  "Act for me"  
LEVEL 3:  + MCP Server          →  "Expose tools as service"
LEVEL 4:  + MCP Client          →  "Consume remote tools"
LEVEL 5a: + Memory              →  "Remember our conversation"
LEVEL 5b: + Async/Streaming     →  "Scale and stream"
LEVEL 5c: + RAG                 →  "Know things beyond training"
LEVEL 5d: + LangGraph           →  "Orchestrate complex workflows"
LEVEL 5e: + Structured Tools    →  "Reliable, typed tool interfaces"
LEVEL 5f: + Multi-Step Reasoning→  "Think step by step"
LEVEL 6:  + Production K8s      →  "Run in real cluster"
```

---

## Running Order for Learning

```bash
# Start simple
python 01-generative_ai.py
python 02-agent.py
python 03-mcp_server.py        # Run in separate terminal
python 04-agent_with_mcp.py    # Connects to 03

# Progressive features
python 05a-agent-with-memory.py
python 05b-async-agent.py
python 05c-agent-with-rag.py
python 05d-langgraph-basics.py
python 05e-class-based-tools.py
python 05f-multi-step-agent.py

# Full system (needs K8s cluster)
python 06-kubernetes-agent.py
```

---

## Key Architectural Patterns by Level

| Pattern | Introduced | File |
|---------|------------|------|
| Tool Calling | Level 2 | `02-agent.py` |
| MCP Protocol | Level 3 | `03-mcp_server.py` |
| Conversation Memory | Level 5a | `05a-agent-with-memory.py` |
| Async Context Manager | Level 5b | `05b-async-agent.py` |
| Streaming Callbacks | Level 5b | `05b-async-agent.py` |
| Concurrent Execution | Level 5b | `05b-async-agent.py` |
| Text Chunking | Level 5c | `05c-agent-with-rag.py` |
| Embedding/Retrieval | Level 5c | `05c-agent-with-rag.py` |
| Prompt Augmentation | Level 5c | `05c-agent-with-rag.py` |
| StateGraph | Level 5d | `05d-langgraph-basics.py` |
| Conditional Edges | Level 5d | `05d-langgraph-basics.py` |
| TypedDict State | Level 5d | `05d-langgraph-basics.py` |
| Abstract Tool Base | Level 5e | `05e-class-based-tools.py` |
| Structured Results | Level 5e | `05e-class-based-tools.py` |
| Analysis Tools | Level 5e | `05e-class-based-tools.py` |
| Plan-and-Execute | Level 5f | `05f-multi-step-agent.py` |
| Reflection Loop | Level 5f | `05f-multi-step-agent.py` |
| Reasoning Trace | Level 5f | `05f-multi-step-agent.py` |
| Vector Database | Level 6 | `06-kubernetes-agent.py` |
| Real Embeddings | Level 6 | `06-kubernetes-agent.py` |
| MCP Server Impl | Level 6 | `06-kubernetes-agent.py` |

---

## Dependencies Progression

```bash
# Level 1-2
pip install ollama langchain-ollama langchain-core langgraph

# Level 3-4 (MCP)
pip install fastmcp langchain-mcp-adapters

# Level 5c (RAG - no external deps, pure Python)
# Already covered

# Level 5d (LangGraph)
pip install langgraph

# Level 6 (Production)
pip install kubernetes chromadb sentence-transformers langchain-chroma langchain-huggingface
# Optional: ollama (for local LLM) or OPENAI_API_KEY
```