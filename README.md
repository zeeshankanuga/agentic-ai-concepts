# Agentic AI Concepts - Progressive Learning Repository

A step-by-step educational journey from basic LLM chat to production-ready Kubernetes agent. Each file builds on the previous, introducing one core concept at a time.

## 🎯 Learning Path

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LEVEL 1:  Basic LLM Chat                  →  ollama.chat()                │
│  LEVEL 2:  Tool-Using Agent                →  @tool + create_agent()       │
│  LEVEL 3:  MCP Server                      →  FastMCP + @mcp.tool          │
│  LEVEL 4:  Agent + MCP Client              →  MultiServerMCPClient         │
│  LEVEL 5a: Conversation Memory             →  Message history + sliding    │
│  LEVEL 5b: Async + Streaming + Concurrent  →  asyncio + callbacks          │
│  LEVEL 5c: RAG (Retrieval-Augmented Gen)   →  Embedding + Vector Search    │
│  LEVEL 5d: LangGraph Workflow              →  StateGraph + Nodes/Edges     │
│  LEVEL 5e: Class-Based Structured Tools    →  BaseTool + ToolResult        │
│  LEVEL 5f: Multi-Step Reasoning            →  Plan→Think→Act→Observe→Reflect│
│  LEVEL 6:  Production K8s Agent            →  Real K8s + ChromaDB + MCP    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 File Structure

| File | Concept | Difficulty | Prerequisites |
|------|---------|------------|---------------|
| `01-generative_ai.py` | Basic LLM loop | ⭐ | ollama |
| `02-agent.py` | Tools + Agent | ⭐⭐ | langchain, ollama |
| `03-mcp_server.py` | MCP Server | ⭐⭐ | fastmcp |
| `04-agent_with_mcp.py` | MCP Client | ⭐⭐ | langchain-mcp-adapters |
| `05a-agent-with-memory.py` | Memory | ⭐⭐⭐ | Level 4 |
| `05b-async-agent.py` | Async Patterns | ⭐⭐⭐ | Level 5a |
| `05c-agent-with-rag.py` | RAG | ⭐⭐⭐ | Level 5a |
| `05d-langgraph-basics.py` | LangGraph | ⭐⭐⭐⭐ | Level 5a |
| `05e-class-based-tools.py` | Structured Tools | ⭐⭐⭐⭐ | Level 5a |
| `05f-multi-step-agent.py` | Multi-Step Reasoning | ⭐⭐⭐⭐ | Level 5d |
| `06-kubernetes-agent.py` | Production System | ⭐⭐⭐⭐⭐ | Level 5f + K8s |

## 🚀 Quick Start

### Prerequisites

```bash
# Core dependencies (Levels 1-5)
pip install ollama langchain-ollama langchain-core langgraph fastmcp langchain-mcp-adapters

# Level 6 (Production)
pip install kubernetes chromadb sentence-transformers langchain-chroma langchain-huggingface

# Start Ollama (for local LLM)
ollama serve
ollama pull gemma4:e4b  # or llama3.1, qwen2.5
```

### Run Each Level

```bash
# Level 1: Basic chat
python 01-generative_ai.py

# Level 2: Agent with local tools
python 02-agent.py

# Level 3: MCP Server (run in separate terminal)
python 03-mcp_server.py

# Level 4: Agent using MCP tools
python 04-agent_with_mcp.py

# Level 5a: Agent with memory
python 05a-agent-with-memory.py

# Level 5b: Async agent with streaming
python 05b-async-agent.py
python 05b-async-agent.py --demo  # See concurrent execution

# Level 5c: RAG-enabled agent
python 05c-agent-with-rag.py
python 05c-agent-with-rag.py --demo  # See retrieval in action

# Level 5d: LangGraph workflow
python 05d-langgraph-basics.py
python 05d-langgraph-basics.py --demo

# Level 5e: Structured tools
python 05e-class-based-tools.py
python 05e-class-based-tools.py --demo

# Level 5f: Multi-step reasoning
python 05f-multi-step-agent.py
python 05f-multi-step-agent.py --demo

# Level 6: Production K8s agent (requires K8s cluster)
python 06-kubernetes-agent.py
```

## 📚 Level-by-Level Guide

### Level 1: Generative AI Basics (`01-generative_ai.py`)

**Concept**: Simple request/response loop with system prompt.

```python
# Core pattern
while True:
    user_input = input("Enter your message:\n")
    response = ollama.chat(model="gemma4:e4b", messages=[system, user])
    print(response['message']['content'])
```

**Key Learn**: LLM as a function: `input → output`

---

### Level 2: Tool-Using Agent (`02-agent.py`)

**Concept**: LLM decides when to call functions (tools).

```python
@tool
def running_containers():
    """Tool:1 Show running Containers"""
    result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
    return result.stdout

agent = create_agent(llm, tools)  # LLM + Tools = Agent
response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
```

**Key Learn**: **Agent = LLM + Tools**. LLM reasons about *which* tool to use.

---

### Level 3: MCP Server (`03-mcp_server.py`)

**Concept**: Expose tools as a standard service (Model Context Protocol).

```python
from fastmcp import FastMCP

mcp = FastMCP("Docker MCP Server")

@mcp.tool
def running_containers():
    """Tool:1 Show running Containers"""
    # ... same logic ...

if __name__ == "__main__":
    mcp.run()  # Listens on stdio for JSON-RPC
```

**Key Learn**: Tools become **language-agnostic services** via MCP.

---

### Level 4: Agent + MCP Client (`04-agent_with_mcp.py`)

**Concept**: Agent discovers and uses remote MCP tools.

```python
client = MultiServerMCPClient({
    "docker-mcp": {"transport": "stdio", "command": "python3", "args": ["03-mcp_server.py"]}
})
tools = await client.get_tools()  # Dynamic tool discovery
agent = create_agent(llm, tools)
```

**Key Learn**: **Decouple** tool providers from tool consumers.

---

### Level 5a: Conversation Memory (`05a-agent-with-memory.py`)

**Concept**: Maintain message history across turns.

```python
messages = [SystemMessage(content=SYSTEM_PROMPT)]

while True:
    user_input = input("You: ")
    messages.append(HumanMessage(content=user_input))
    
    # Context window management (sliding window)
    if len(messages) > MAX_MESSAGES:
        messages = [messages[0]] + messages[-(MAX_MESSAGES - 1):]
    
    response = await agent.ainvoke({"messages": messages})
    messages.append(response['messages'][-1])  # Add AI response to history
```

**Key Learn**: **Stateful conversations** via message list + context window.

---

### Level 5b: Async + Streaming + Concurrent (`05b-async-agent.py`)

**Concept**: Production async patterns.

```python
class AsyncDockerAgent:
    async def __aenter__(self):
        self.client = MultiServerMCPClient(...)
        tools = await self.client.get_tools()
        self.agent = create_agent(llm, tools, callbacks=[StreamingCallbackHandler()])
        return self
    
    async def __aexit__(self, *args):
        await self.client.close()
    
    async def run_concurrent_queries(self, queries):
        # Run multiple queries IN PARALLEL
        return await asyncio.gather(*[self.single_query(q) for q in queries])
```

**Key Learn**: **AsyncContextManager**, **StreamingCallbacks**, **asyncio.gather** for concurrency.

---

### Level 5c: RAG (Retrieval-Augmented Generation) (`05c-agent-with-rag.py`)

**Concept**: Retrieve relevant knowledge before generating.

```
User Query → Embedding → Vector Search → Top-K Chunks → Augmented Prompt → LLM
```

```python
class InMemoryKnowledgeBase:
    def search(self, query, k=3):
        # TF-IDF style scoring (no external deps)
        results = []
        for doc in self.documents:
            for chunk in doc.chunks:
                score = self.embedder.score(query, chunk)
                if score > 0:
                    results.append(RetrievalResult(doc, chunk, score))
        return sorted(results, key=lambda r: r.score, reverse=True)[:k]

# Augment prompt with retrieved context
augmented_prompt = f"""
{retrieved_context}

USER QUESTION: {user_query}
"""
```

**Key Learn**: **Chunking**, **Embedding**, **Retrieval**, **Prompt Augmentation** - the RAG pipeline.

---

### Level 5d: LangGraph Workflow (`05d-langgraph-basics.py`)

**Concept**: Explicit graph of nodes with shared state.

```python
class AgentState(TypedDict):
    user_query: str
    rewritten_query: str
    retrieved_context: str
    tool_calls: List[Dict]
    tool_results: List[Dict]
    final_answer: str

def rewrite_query(state): ...
def retrieve(state): ...
def decide_action(state): ...
def execute_tools(state): ...
def synthesize(state): ...

workflow = StateGraph(AgentState)
workflow.add_node("rewrite_query", rewrite_query)
workflow.add_node("retrieve", retrieve)
workflow.add_node("decide_action", decide_action)
workflow.add_node("execute_tools", execute_tools)
workflow.add_node("synthesize", synthesize)

workflow.set_entry_point("rewrite_query")
workflow.add_edge("rewrite_query", "retrieve")
workflow.add_edge("retrieve", "decide_action")
workflow.add_conditional_edges("decide_action", route_after_decide)
workflow.add_edge("execute_tools", "synthesize")
workflow.add_edge("synthesize", END)

graph = workflow.compile()
result = graph.invoke(initial_state)
```

**Key Learn**: **StateGraph**, **TypedDict State**, **Nodes**, **Conditional Edges**, **Compilation**.

---

### Level 5e: Class-Based Structured Tools (`05e-class-based-tools.py`)

**Concept**: Tools as classes with structured I/O.

```python
@dataclass
class ToolResult:
    status: ToolStatus  # SUCCESS | ERROR | PARTIAL
    data: Any = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

class BaseTool(ABC):
    @property @abstractmethod def name(self): ...
    @property @abstractmethod def description(self): ...
    @property @abstractmethod def input_schema(self): ...
    @abstractmethod def execute(self, **kwargs) -> ToolResult: ...

class ListContainersTool(BaseTool):
    def __init__(self, docker_tools: DockerToolSet):  # Dependency injection
        self.docker = docker_tools
    
    def execute(self, all: bool = False, format: str = "table") -> ToolResult:
        # Returns structured data, not raw string
        return ToolResult.success(data={"containers": [...], "count": 5}, format=format)

# Analysis tools with BUILT-IN LOGIC
class AnalysisToolSet:
    def analyze_container_health(self, container: str) -> ToolResult:
        # Does the analysis that would need multiple LLM steps
        issues = []
        if container_data["State"]["OOMKilled"]:
            issues.append("OOMKilled - increase memory limit")
        return ToolResult.success(data={"issues": issues, "recommendations": [...]})
```

**Key Learn**: **Dependency Injection**, **Structured Results**, **Analysis Tools** (logic in tools, not prompts).

---

### Level 5f: Multi-Step Reasoning (`05f-multi-step-agent.py`)

**Concept**: Explicit Plan → Think → Act → Observe → Reflect loop.

```python
class StepType(Enum):
    PLAN = "plan"
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    SYNTHESIZE = "synthesize"

async def run(self, query):
    # Phase 1: PLAN
    plan = await self.plan(query)  # Creates AgentPlan with steps
    
    # Phase 2: EXECUTE with REFLECTION
    while plan.current_step < len(plan.steps):
        await self.execute_step(plan, plan.current_step, query)
        should_continue = await self.reflect(plan, query)  # Can add steps!
        if not should_continue: break
    
    # Phase 3: SYNTHESIZE
    answer = await self.synthesize(query)
```

**Key Learn**: **Plan-and-Execute**, **Reflection Loop**, **Visible Reasoning Trace**, **Dynamic Plan Adjustment**.

---

### Level 6: Production Kubernetes Agent (`06-kubernetes-agent.py`)

**Concept**: All patterns combined in a real system.

```python
# Real Vector DB
kb = KnowledgeBase()  # ChromaDB + HuggingFaceEmbeddings (MiniLM-L6-v2)
kb.add_knowledge(k8s_docs)  # Chunk → Embed → Store

# Real K8s Tools
class KubernetesTools:
    def list_pods(self, namespace="default"):
        pods = self.k8s.core_v1.list_namespaced_pod(namespace)
        return {"pods": [...], "count": len(pods)}
    
    def analyze_pod(self, pod_name, namespace="default"):
        # Real issue detection: CrashLoopBackOff, OOMKilled, high restarts
        return {"issues": [...], "phase": pod.status.phase}

# LangGraph with 5 nodes (production version of Level 5d)
agent_graph = build_agent_graph(k8s_tools, kb, llm)

# MCP Server for external access
server = MCPServer(agent_graph, k8s_tools)
server.run()  # JSON-RPC over stdio
```

**Key Learn**: **ChromaDB**, **Sentence Transformers**, **Kubernetes Python Client**, **MCP Server Implementation**, **In-Cluster Auth**.

---

## 🧠 Concept Map

```
┌────────────────────────────────────────────────────────────────────┐
│                        AGENTIC AI STACK                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐                                                   │
│  │   LLM       │  ← Level 1: Core reasoning engine                │
│  │  (Ollama)   │                                                   │
│  └──────┬──────┘                                                   │
│         │                                                          │
│  ┌──────▼──────┐                                                   │
│  │   TOOLS     │  ← Level 2,3,4: Action execution                 │
│  │  @tool/MCP  │                                                   │
│  └──────┬──────┘                                                   │
│         │                                                          │
│  ┌──────▼──────┐     ┌─────────────┐                               │
│  │   MEMORY    │     │    RAG      │  ← Level 5a, 5c: Knowledge   │
│  │  Messages   │     │  Vector DB  │       + Context              │
│  └──────┬──────┘     └──────┬──────┘                               │
│         │                   │                                      │
│  ┌──────▼───────────────────▼──────┐                               │
│  │      ORCHESTRATION              │  ← Level 5d, 5f: Control     │
│  │   LangGraph + Multi-Step        │       Flow + Reasoning       │
│  └──────┬───────────────────┬──────┘                               │
│         │                   │                                      │
│  ┌──────▼──────┐     ┌──────▼──────┐                               │
│  │  STRUCTURED │     │  PRODUCTION │  ← Level 5e, 6: Reliability  │
│  │   TOOLS     │     │  (K8s/MCP)  │       + Scale                │
│  └─────────────┘     └─────────────┘                               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## 🔑 Key Patterns Reference

| Pattern | When to Use | Example |
|---------|-------------|---------|
| **Tool Calling** | LLM needs external data/action | Docker ops, API calls |
| **MCP** | Share tools across languages/agents | Team tool server |
| **Memory** | Multi-turn conversations | Chat agents |
| **Streaming** | Long responses, better UX | Code generation |
| **Concurrency** | Multiple independent queries | Batch analysis |
| **RAG** | Domain knowledge beyond training | Troubleshooting guides |
| **LangGraph** | Complex multi-step workflows | CI/CD pipelines |
| **Structured Tools** | Reliable tool interfaces | Production systems |
| **Multi-Step** | Complex reasoning needed | Root cause analysis |
| **Vector DB** | Semantic search at scale | Large knowledge bases |

## 📖 Further Reading

- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [ChromaDB](https://www.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)

## 🤝 Contributing

This is a learning repository. Each level should:
1. Introduce **exactly one** new concept
2. Include **inline comments** explaining the concept
3. Have a `--demo` mode for non-interactive testing
4. Build on the previous level's patterns

---

## 👩‍💻 Author

**Zeeshan kanuga** — Technical Architect |DevOps Engineer | Platform Engineering | AI-Augmented DevOps

Built by [Zeeshan Kanuga](https://github.com/zeeshankanuga)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/zeeshankanuga/)

---

**Happy Learning!** 🎓 Start with `01-generative_ai.py` and progress through each level.