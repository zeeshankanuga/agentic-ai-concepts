# Agentic AI Concepts — Learning Progression

A hands-on educational repository demonstrating **core Agentic AI concepts** through 5 progressive implementations, from basic LLM completion to a full agentic system.

## 🎯 Learning Objectives

This project teaches you how Agentic AI works end-to-end by building increasingly sophisticated agents:

| Level | File | Concept | Key Learning |
|-------|------|---------|--------------|
| **0** | `01-generative_ai.py` | Pure LLM Completion | Stateless chat, no tools, no memory |
| **1** | `02-agent.py` | ReAct Agent (Direct Tools) | Reasoning + Acting loop with inline tools |
| **1b** | `03-mcp_server.py` | MCP Server (Tool Provider) | Exposing tools via Model Context Protocol |
| **2** | `04-agent_with_mcp.py` | MCP Client Agent | Consuming MCP tools from external server |
| **3** | `05-kubernetes-agent.py` | Full Agentic System | LangGraph workflow, RAG, typed state, MCP server |

---

## 📁 Directory Structure

```
agentic-ai-concepts/
├── 01-generative_ai.py       # L0: Pure LLM completion (Ollama)
├── 02-agent.py               # L1: ReAct agent with direct @tool functions
├── 03-mcp_server.py          # L1b: FastMCP server exposing Docker tools
├── 04-agent_with_mcp.py      # L2: MCP client agent consuming tools via stdio
├── 05-kubernetes-agent.py    # L3: Full agentic system (LangGraph + RAG + MCP)
├── agentic-ai-core-concept.md # 45 core concepts explained (plain English)
├── difference.md              # Architecture comparison of all 5 levels
├── all-agentic-ai-concepts.md # Additional reference material
├── core-concept.md            # Core concept summaries
└── README.md                  # This file
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.10+ | Runtime |
| **Ollama** | Latest | Local LLM server (or OpenAI API key) |
| **pip** | Latest | Package manager |

### Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install base dependencies (for L0-L2)
pip install --upgrade pip
pip install ollama langchain langchain-ollama langchain-core langchain-mcp-adapters fastmcp

# For L3 (kubernetes-agent.py) - additional dependencies
pip install langgraph langchain-chroma langchain-huggingface chromadb sentence-transformers kubernetes
```

> **Note**: For L3, you'll also need a running Kubernetes cluster (KIND, minikube, or cloud) and `kubectl` configured. Or use the mock LLM fallback for testing without a cluster.

### Start Ollama (for local LLM)

```bash
ollama serve &
ollama pull llama3.1
```

---

## 📚 Learning Path — Run in Order

### Level 0: Pure LLM Completion
```bash
python3 01-generative_ai.py
```
- Simple chat loop with system prompt
- No tools, no memory, no reasoning loop
- **Concepts**: Tokenization, Transformer, Attention, LLM, RLHF

### Level 1: ReAct Agent with Direct Tools
```bash
python3 02-agent.py
```
- Agent reasons, calls tools, observes, repeats
- Tools defined inline with `@tool` decorator
- Uses `subprocess` to call Docker CLI
- **Concepts**: Tool Calling, ReAct Pattern, Chain of Thought, Direct Integration

### Level 1b: MCP Server (Tool Provider)
```bash
python3 03-mcp_server.py
```
- Exposes same Docker tools via MCP protocol
- Run this in one terminal, keep it running
- **Concepts**: MCP Protocol, MCP Server, JSON-RPC over stdio

### Level 2: MCP Client Agent
```bash
# Terminal 1: Start MCP server
python3 03-mcp_server.py

# Terminal 2: Run MCP client agent
python3 04-agent_with_mcp.py
```
- Discovers tools dynamically from MCP server
- Same ReAct agent, different tool source
- Async communication via stdio
- **Concepts**: MCP Client, Dynamic Tool Discovery, Async Execution

### Level 3: Full Agentic System
```bash
# Option A: Run as CLI agent (interactive)
python3 05-kubernetes-agent.py

# Option B: Run as MCP server (for other agents to consume)
# The file includes both modes - see code for MCPServer class
```
- LangGraph multi-node workflow (5 nodes)
- RAG with ChromaDB + MiniLM embeddings
- Typed state management (TypedDict)
- Kubernetes API tools (or mock for testing)
- Custom MCP server implementation
- **Concepts**: LangGraph, StateGraph, Nodes/Edges, RAG, Vector DB, Embeddings, API Tools, Class-based Tools, Structured Results, Multi-LLM Factory, Custom MCP, Agent-as-MCP, Logging, Error Handling

---

## 📖 Documentation Files

| File | Purpose |
|------|---------|
| **`agentic-ai-core-concept.md`** | 45 core concepts explained in plain English with analogies, examples, and learning sequence |
| **`difference.md`** | Detailed architecture comparison of all 5 levels with code structure, pros/cons, and progression summary |
| **`all-agentic-ai-concepts.md`** | Additional reference material |
| **`core-concept.md`** | Core concept summaries |

---

## 🔑 Key Concepts by Level

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLEXITY EVOLUTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L0: generative_ai.py       →  LLM only (completion)                      │
│       │                                                                │
│       ▼                                                                │
│  L1: agent.py               →  ReAct + Direct Tools                     │
│       │                                                                │
│       ├──▶ L1b: mcp_server.py    →  MCP Server (protocol)              │
│       │                                                                │
│       └──▶ L2: agent_with_mcp.py →  MCP Client (consumes protocol)     │
│                                                                │
│       ▼                                                                │
│  L3: kubernetes-agent.py    →  Full System                             │
│       ┌──────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│       │Rewrite│→│Retrieve│→│ Decide │→│ Execute│→│Synthesize│          │
│       │ Query │  │ (RAG)  │  │ Action │  │ Tools  │  │ Answer   │          │
│       └──────┘ └──────┘ └────────┘ └────────┘ └────────┘              │
│            │         │          │           │          │                │
│            ▼         ▼          ▼           ▼          ▼                │
│       KnowledgeBase  │    KubernetesTools    │    MCP Server           │
│       (ChromaDB)     │    (K8s API)          │    (JSON-RPC)           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Customization Ideas

### Add Tools to Level 1 (`02-agent.py`)
```python
@tool
def my_custom_tool(input: str) -> str:
    """Description for the LLM."""
    return f"Processed: {input}"

tools = [running_containers, container_logs_by_name, my_custom_tool]
```

### Add Tools to MCP Server (`03-mcp_server.py`)
```python
@mcp.tool
def my_custom_tool(input: str) -> str:
    """Description for the LLM."""
    return f"Processed: {input}"
```

### Extend Level 3 Knowledge Base
```python
# In KnowledgeBase.add_knowledge()
knowledge_docs.append({
    "source": "my-docs",
    "topic": "my-topic",
    "content": "Your domain knowledge here..."
})
```

### Switch LLM Provider (Level 3)
```python
# In create_llm() - uncomment for OpenAI
# export OPENAI_API_KEY=sk-...
# return ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Or use different Ollama model
# return ChatOllama(model="qwen2.5:7b", temperature=0)
```

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Activate venv and `pip install -r requirements.txt` (or install packages per level) |
| Ollama connection failed | Ensure `ollama serve` is running; check `curl http://localhost:11434/api/tags` |
| MCP server not found | Run `03-mcp_server.py` in separate terminal before `04-agent_with_mcp.py` |
| K8s permission errors (L3) | Configure RBAC or use mock LLM fallback (no cluster needed) |
| ChromaDB empty (L3) | Knowledge base auto-populates on first run; check `./chroma_db` directory |

---

## 📖 Further Reading

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **MCP Specification**: https://modelcontextprotocol.io/
- **RAG Pattern**: https://www.pinecone.io/learn/retrieval-augmented-generation/
- **ChromaDB**: https://docs.trychroma.com/
- **Kubernetes Python Client**: https://github.com/kubernetes-client/python

---

## 👩‍💻 Author

**Zeeshan Kanuga** — Technical Architect | DevOps Engineer | Platform Engineering | AI-Augmented DevOps

Built by [Zeeshan Kanuga](https://github.com/zeeshankanuga)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/zeeshankanuga/)
---

## 📄 License

MIT License — Educational use encouraged!

---

**Built for learning Agentic AI concepts progressively** 🚀