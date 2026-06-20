#!/usr/bin/env python3
"""
Kubernetes MCP Agent - Learning Edition

Educational implementation showing core Agentic AI concepts:
1. Input Processing → User prompt comes in
2. Embedding → Convert text to vectors for semantic search
3. Chunking → Split large documents into manageable pieces
4. Vector DB → Store/retrieve relevant context (using ChromaDB)
5. LLM Calling → Generate responses with retrieved context
6. Tool Execution → MCP tools for Kubernetes actions
7. LangGraph → Orchestrate the agent workflow

This version uses 3 simple tools for clarity:
- list_pods: List pods in a namespace
- get_pod_logs: Get logs from a pod
- analyze_pod: Simple issue detection

Architecture:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User       │────▶│  Embedding  │────▶│  Vector DB  │────▶│  LLM +      │
│  Prompt     │     │  (MiniLM)   │     │  (Chroma)   │     │  Tools      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    "What pods          Similar           "Here are
                     are failing?"      docs +             the pods
                                       tools"             + analysis"
"""

import json
import sys
import os
import logging
from typing import Dict, List, Any, Optional, TypedDict
from dataclasses import dataclass, asdict
from datetime import datetime

# =============================================================================
# DEPENDENCIES - Install with: pip install kubernetes langchain langgraph chromadb sentence-transformers
# =============================================================================

# Kubernetes
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

# LangChain / LangGraph for agentic workflow
try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.tools import tool
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langgraph.graph import StateGraph, END
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Local LLM (Ollama) or OpenAI
try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger("k8s-agent-learning")


# =============================================================================
# STEP 1: DATA MODELS & STATE (LangGraph State)
# =============================================================================

class AgentState(TypedDict):
    """
    LangGraph State - The shared memory that flows through the agent workflow.
    
    Each node in the graph can read/write to this state.
    This is how agents maintain context across steps.
    """
    user_query: str                    # Original user question
    rewritten_query: str               # Query optimized for retrieval
    retrieved_docs: List[str]          # Documents from vector DB
    tool_calls: List[Dict]             # Tools the LLM decided to call
    tool_results: List[Dict]           # Results from tool execution
    final_answer: str                  # Final response to user
    error: Optional[str]               # Any error messages


@dataclass
class MCPTool:
    """MCP Tool definition for LLM function calling."""
    name: str
    description: str
    input_schema: Dict[str, Any]


# =============================================================================
# STEP 2: KUBERNETES MANAGER (Cluster Connection)
# =============================================================================

class KubernetesManager:
    """
    Manages Kubernetes API client.
    Handles both in-cluster (KIND pod) and local kubeconfig.
    """
    
    def __init__(self):
        self.core_v1: Optional[client.CoreV1Api] = None
        self._ready = False
    
    def initialize(self) -> bool:
        """Initialize K8s client - tries in-cluster first, then kubeconfig."""
        if not KUBERNETES_AVAILABLE:
            logger.error("Install kubernetes: pip install kubernetes")
            return False
        
        try:
            # In KIND cluster, this works automatically via service account
            try:
                config.load_incluster_config()
                logger.info("✓ Using in-cluster config (KIND pod)")
            except config.ConfigException:
                # Local development
                config.load_kube_config()
                logger.info("✓ Using kubeconfig file")
            
            self.core_v1 = client.CoreV1Api()
            # Test connection
            self.core_v1.get_api_resources()
            self._ready = True
            return True
        except Exception as e:
            logger.error(f"K8s init failed: {e}")
            return False
    
    def is_ready(self) -> bool:
        return self._ready


# =============================================================================
# STEP 3: VECTOR DATABASE SETUP (ChromaDB + Embeddings)
# =============================================================================

class KnowledgeBase:
    """
    Vector Database for Agentic AI Knowledge.
    
    CONCEPTS DEMONSTRATED:
    - Embedding: Convert text → numerical vectors (semantic meaning)
    - Chunking: Split large docs → small pieces (fit in context window)
    - Vector DB: Store vectors + metadata for similarity search
    - Retrieval: Find relevant context for user query
    """
    
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None
        
        if LANGCHAIN_AVAILABLE:
            self._initialize()
    
    def _initialize(self):
        """Initialize embeddings, chunker, and vector store."""
        
        # EMBEDDING MODEL: sentence-transformers/all-MiniLM-L6-v2
        # - 384 dimensions (small, fast)
        # - Good for semantic similarity
        # - Runs locally, no API key needed
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # CHUNKING: Split documents into overlapping chunks
        # - chunk_size: Max tokens per chunk (~500 chars ≈ 128 tokens)
        # - chunk_overlap: Overlap to maintain context between chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # VECTOR STORE: ChromaDB (local, persistent)
        # - Stores: vector + document + metadata
        # - Supports similarity search with metadata filtering
        self.vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name="k8s_knowledge"
        )
        
        logger.info(f"✓ Vector DB ready at {self.persist_dir}")
    
    def add_knowledge(self, documents: List[Dict[str, str]]):
        """
        Add documents to vector DB.
        
        Process: Document → Chunk → Embed → Store
        """
        if not self.vectorstore:
            return
        
        texts = []
        metadatas = []
        
        for doc in documents:
            # Chunk the document
            chunks = self.text_splitter.split_text(doc["content"])
            
            for i, chunk in enumerate(chunks):
                texts.append(chunk)
                metadatas.append({
                    "source": doc.get("source", "unknown"),
                    "chunk_id": i,
                    "topic": doc.get("topic", "general")
                })
        
        # Embed and store (Chroma handles embedding internally)
        self.vectorstore.add_texts(texts=texts, metadatas=metadatas)
        logger.info(f"✓ Added {len(texts)} chunks to vector DB")
    
    def search(self, query: str, k: int = 3) -> List[str]:
        """
        Semantic search: Query → Embed → Find similar vectors → Return docs.
        
        This is RAG (Retrieval-Augmented Generation) in action!
        """
        if not self.vectorstore:
            return []
        
        # Similarity search returns (doc, score) tuples
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        
        docs = []
        for doc, score in results:
            docs.append(f"[Score: {score:.3f}] {doc.page_content}")
        
        logger.info(f"✓ Retrieved {len(docs)} relevant chunks for: '{query[:50]}...'")
        return docs


# =============================================================================
# STEP 4: MCP TOOLS (Simple 3 Tools for Learning)
# =============================================================================

class KubernetesTools:
    """
    Simple Kubernetes Tools - Only 3 for learning clarity.
    
    Each tool is a Python function that the LLM can call via MCP.
    In LangChain, we use @tool decorator for automatic schema generation.
    """
    
    def __init__(self, k8s: KubernetesManager):
        self.k8s = k8s
    
    # Tool 1: List Pods
    def list_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """List all pods in a namespace with basic status."""
        try:
            pods = self.k8s.core_v1.list_namespaced_pod(namespace=namespace)
            result = []
            for p in pods.items:
                restarts = sum(c.restart_count for c in (p.status.container_statuses or []))
                result.append({
                    "name": p.metadata.name,
                    "status": p.status.phase,
                    "restarts": restarts,
                    "node": p.spec.node_name,
                    "age": str(datetime.now() - p.metadata.creation_timestamp.replace(tzinfo=None)) if p.metadata.creation_timestamp else "unknown"
                })
            return {"pods": result, "count": len(result)}
        except Exception as e:
            return {"error": str(e)}
    
    # Tool 2: Get Pod Logs
    def get_pod_logs(self, pod_name: str, namespace: str = "default", tail_lines: int = 50) -> Dict[str, Any]:
        """Get recent logs from a pod."""
        try:
            logs = self.k8s.core_v1.read_namespaced_pod_log(
                name=pod_name, namespace=namespace, tail_lines=tail_lines
            )
            return {"pod_name": pod_name, "logs": logs}
        except Exception as e:
            return {"error": str(e)}
    
    # Tool 3: Simple Pod Analysis
    def analyze_pod(self, pod_name: str, namespace: str = "default") -> Dict[str, Any]:
        """Basic issue detection for a pod."""
        try:
            pod = self.k8s.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            issues = []
            
            for cs in (pod.status.container_statuses or []):
                if cs.state and cs.state.waiting:
                    reason = cs.state.waiting.reason
                    if reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "RunContainerError"]:
                        issues.append(f"⚠️ {cs.name}: {reason} - {cs.state.waiting.message}")
                if cs.state and cs.state.terminated and cs.state.terminated.reason == "OOMKilled":
                    issues.append(f"💥 {cs.name}: OOMKilled (out of memory)")
                if cs.restart_count > 3:
                    issues.append(f"🔄 {cs.name}: High restarts ({cs.restart_count})")
            
            if not issues:
                issues.append("✅ No obvious issues detected")
            
            return {"pod_name": pod_name, "phase": pod.status.phase, "issues": issues}
        except Exception as e:
            return {"error": str(e)}
    
    def get_tool_definitions(self) -> List[MCPTool]:
        """Return MCP tool definitions for LLM function calling."""
        return [
            MCPTool(
                name="list_pods",
                description="List all pods in a namespace with status and restart count",
                input_schema={"type": "object", "properties": {"namespace": {"type": "string", "default": "default"}}, "required": []}
            ),
            MCPTool(
                name="get_pod_logs",
                description="Get recent logs from a specific pod",
                input_schema={"type": "object", "properties": {"pod_name": {"type": "string"}, "namespace": {"type": "string", "default": "default"}, "tail_lines": {"type": "integer", "default": 50}}, "required": ["pod_name"]}
            ),
            MCPTool(
                name="analyze_pod",
                description="Analyze a pod for common issues (CrashLoopBackOff, OOMKilled, high restarts)",
                input_schema={"type": "object", "properties": {"pod_name": {"type": "string"}, "namespace": {"type": "string", "default": "default"}}, "required": ["pod_name"]}
            )
        ]


# =============================================================================
# STEP 5: LLM SETUP (Local Ollama or OpenAI)
# =============================================================================

def create_llm():
    """
    Create LLM instance for the agent.
    
    Options (in priority order):
    1. Ollama (local, free) - e.g., llama3.1, qwen2.5
    2. OpenAI (cloud, paid) - gpt-4o-mini
    3. Mock for testing without API
    """
    if OLLAMA_AVAILABLE:
        try:
            # Uses local Ollama server (default: http://localhost:11434)
            # Make sure: ollama pull llama3.1
            return ChatOllama(model="llama3.1", temperature=0)
        except Exception:
            pass
    
    if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Fallback: Mock LLM for testing
    class MockLLM:
        def invoke(self, messages):
            # Simple keyword-based responses for demo
            content = str(messages[-1].content if messages else "")
            if "pod" in content.lower() and "list" in content.lower():
                return AIMessage(content='{"tool": "list_pods", "args": {"namespace": "default"}}')
            elif "log" in content.lower():
                return AIMessage(content='{"tool": "get_pod_logs", "args": {"pod_name": "example-pod"}}')
            elif "analyz" in content.lower():
                return AIMessage(content='{"tool": "analyze_pod", "args": {"pod_name": "example-pod"}}')
            return AIMessage(content="I can help you check pods, logs, or analyze issues. What would you like to do?")
    
    logger.warning("⚠️ Using Mock LLM - install Ollama or set OPENAI_API_KEY for real LLM")
    return MockLLM()


# =============================================================================
# STEP 6: LANGGRAPH WORKFLOW (Agent Orchestration)
# =============================================================================

def build_agent_graph(k8s_tools: KubernetesTools, knowledge_base: KnowledgeBase, llm):
    """
    Build the LangGraph workflow for the agent.
    
    GRAPH NODES (each is a step in the agent's thinking process):
    
    1. rewrite_query   → Optimize user query for retrieval
    2. retrieve        → Search vector DB for relevant context
    3. decide_action   → LLM decides: answer directly or call tools
    4. execute_tools   → Run MCP tools on Kubernetes
    5. synthesize      → Combine tool results + context → final answer
    
    FLOW: rewrite → retrieve → decide → (execute_tools → synthesize) OR synthesize
    """
    
    # Node 1: Query Rewriting
    def rewrite_query(state: AgentState) -> AgentState:
        """Rewrite user query for better vector search."""
        query = state["user_query"]
        # Simple rewrite: add Kubernetes context
        rewritten = f"Kubernetes troubleshooting: {query}"
        logger.info(f"🔄 Rewritten query: {rewritten}")
        return {**state, "rewritten_query": rewritten}
    
    # Node 2: Vector DB Retrieval (RAG)
    def retrieve(state: AgentState) -> AgentState:
        """Retrieve relevant knowledge from vector database."""
        docs = knowledge_base.search(state["rewritten_query"], k=3)
        logger.info(f"📚 Retrieved {len(docs)} knowledge chunks")
        return {**state, "retrieved_docs": docs}
    
    # Node 3: LLM Decides Action
    def decide_action(state: AgentState) -> AgentState:
        """
        LLM decides whether to:
        - Answer directly (if knowledge is sufficient)
        - Call tools (if live cluster data needed)
        """
        # Build context from retrieved docs
        context = "\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "No relevant knowledge found."
        
        # Available tools
        tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in k8s_tools.get_tool_definitions()])
        
        prompt = f"""You are a Kubernetes expert. Decide the next action.

CONTEXT FROM KNOWLEDGE BASE:
{context}

AVAILABLE TOOLS:
{tools_desc}

USER QUERY: {state["user_query"]}

RESPOND WITH JSON ONLY:
{{
  "action": "tool_call" | "direct_answer",
  "tool": "tool_name_if_needed",
  "args": {{"param": "value"}},
  "reasoning": "why this action"
}}"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        
        try:
            decision = json.loads(response.content)
            logger.info(f"🤔 LLM Decision: {decision['action']} - {decision.get('reasoning', '')}")
            
            if decision["action"] == "tool_call":
                return {**state, "tool_calls": [{"tool": decision["tool"], "args": decision["args"]}]}
            else:
                return {**state, "final_answer": decision.get("reasoning", "Done")}
        except json.JSONDecodeError:
            # Fallback: direct answer
            return {**state, "final_answer": response.content}
    
    # Node 4: Execute Tools
    def execute_tools(state: AgentState) -> AgentState:
        """Execute the tool calls on Kubernetes cluster."""
        results = []
        
        for call in state.get("tool_calls", []):
            tool_name = call["tool"]
            args = call["args"]
            logger.info(f"🔧 Executing tool: {tool_name} with {args}")
            
            method = getattr(k8s_tools, tool_name, None)
            if method:
                result = method(**args)
                results.append({"tool": tool_name, "result": result})
            else:
                results.append({"tool": tool_name, "result": {"error": "Unknown tool"}})
        
        return {**state, "tool_results": results}
    
    # Node 5: Synthesize Final Answer
    def synthesize(state: AgentState) -> AgentState:
        """Combine tool results and knowledge into final answer."""
        tool_results = state.get("tool_results", [])
        context = "\n".join(state.get("retrieved_docs", []))
        
        results_text = "\n".join([
            f"Tool {r['tool']} result: {json.dumps(r['result'], indent=2)}"
            for r in tool_results
        ])
        
        prompt = f"""You are a Kubernetes expert. Provide a clear, helpful answer.

KNOWLEDGE BASE CONTEXT:
{context}

TOOL EXECUTION RESULTS:
{results_text}

ORIGINAL QUESTION: {state["user_query"]}

Provide a concise answer with:
1. Direct answer to the question
2. Any issues found
3. Recommended next steps"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        return {**state, "final_answer": response.content}
    
    # Router: Decide whether to execute tools or go to synthesis
    def route_after_decide(state: AgentState) -> str:
        if state.get("tool_calls"):
            return "execute_tools"
        return "synthesize"
    
    # BUILD THE GRAPH
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("decide_action", decide_action)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("synthesize", synthesize)
    
    # Add edges (flow)
    workflow.set_entry_point("rewrite_query")
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("retrieve", "decide_action")
    workflow.add_conditional_edges("decide_action", route_after_decide)
    workflow.add_edge("execute_tools", "synthesize")
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()


# =============================================================================
# STEP 7: MCP SERVER (JSON-RPC over stdio)
# =============================================================================

class MCPServer:
    """Simple MCP Server for stdio communication."""
    
    def __init__(self, agent_graph, k8s_tools: KubernetesTools):
        self.agent = agent_graph
        self.tools = k8s_tools
    
    def handle_request(self, request: Dict) -> Dict:
        """Process MCP JSON-RPC request."""
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})
        
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "k8s-learning-agent", "version": "1.0"}
            }}
        
        elif method == "tools/list":
            tool_defs = self.tools.get_tool_definitions()
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tool_defs]
            }}
        
        elif method == "tools/call":
            # For MCP tools/call, we run the agent graph with the user query
            # The tool name becomes part of the user query context
            tool_name = params.get("name")
            args = params.get("arguments", {})
            user_query = f"Use {tool_name} tool with arguments: {json.dumps(args)}"
            
            # Run agent workflow
            initial_state: AgentState = {
                "user_query": user_query,
                "rewritten_query": "",
                "retrieved_docs": [],
                "tool_calls": [],
                "tool_results": [],
                "final_answer": "",
                "error": None
            }
            
            final_state = self.agent.invoke(initial_state)
            answer = final_state.get("final_answer", "No answer generated")
            
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": answer}]
            }}
        
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
    
    def run(self):
        """Main stdio loop."""
        logger.info("🚀 Kubernetes Learning Agent MCP Server started")
        logger.info("   Listening on stdio for JSON-RPC requests...")
        
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")


# =============================================================================
# STEP 8: INITIALIZE KNOWLEDGE BASE (Sample K8s Knowledge)
# =============================================================================

def setup_knowledge_base(kb: KnowledgeBase):
    """Populate vector DB with Kubernetes troubleshooting knowledge."""
    
    knowledge_docs = [
        {
            "source": "k8s-docs",
            "topic": "pod-lifecycle",
            "content": """Pod Lifecycle Phases:
- Pending: Pod accepted but containers not created (scheduling, image pull)
- Running: All containers created, at least one running
- Succeeded: All containers terminated successfully
- Failed: All containers terminated, at least one failed
- Unknown: State cannot be determined"""
        },
        {
            "source": "k8s-docs",
            "topic": "common-issues",
            "content": """Common Pod Issues:
- CrashLoopBackOff: Container crashes repeatedly. Check logs with 'kubectl logs'. Common causes: app bugs, config errors, port conflicts, OOM.
- ImagePullBackOff: Cannot pull container image. Check image name, tag, registry credentials (imagePullSecrets), network access.
- ErrImagePull: Image pull error. Similar to ImagePullBackOff but immediate failure.
- OOMKilled: Container exceeded memory limit. Increase memory limit in resources or optimize app.
- Pending: Pod not scheduled. Check node resources, taints/tolerations, affinity, PVC binding.
- ContainerCreating: Stuck creating. Check CNI, volume mounts, image pull secrets."""
        },
        {
            "source": "k8s-docs",
            "topic": "debugging-commands",
            "content": """Essential Debugging Commands:
- kubectl get pods -n <namespace> -o wide     # List pods with node, IP
- kubectl describe pod <pod> -n <namespace>   # Full details + events
- kubectl logs <pod> -n <namespace> -c <container>  # Container logs
- kubectl logs <pod> -n <namespace> --previous    # Previous container logs
- kubectl top pods -n <namespace>             # Resource usage (needs metrics-server)
- kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp  # Recent events"""
        },
        {
            "source": "k8s-docs",
            "topic": "resource-management",
            "content": """Resource Requests and Limits:
- requests: Minimum guaranteed resources (scheduler uses this)
- limits: Maximum allowed resources (enforced by kubelet)
- QoS Classes:
  * Guaranteed: requests == limits for all containers
  * Burstable: requests < limits, or only requests set
  * BestEffort: No requests or limits set (lowest priority)
- OOMKilled happens when container exceeds memory limit
- CPU throttling happens when container exceeds CPU limit"""
        }
    ]
    
    kb.add_knowledge(knowledge_docs)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Initialize and run the Kubernetes Learning Agent."""
    
    print("=" * 60)
    print("🧠 KUBERNETES LEARNING AGENT - Agentic AI Demo")
    print("=" * 60)
    
    # 1. Initialize Kubernetes
    k8s = KubernetesManager()
    if not k8s.initialize():
        print("❌ Failed to connect to Kubernetes. Exiting.")
        sys.exit(1)
    
    # 2. Initialize Knowledge Base (Vector DB + Embeddings)
    kb = KnowledgeBase()
    if not LANGCHAIN_AVAILABLE:
        print("❌ LangChain not available. Install: pip install langchain langgraph chromadb sentence-transformers")
        sys.exit(1)
    
    setup_knowledge_base(kb)
    
    # 3. Initialize Tools
    k8s_tools = KubernetesTools(k8s)
    
    # 4. Initialize LLM
    llm = create_llm()
    
    # 5. Build LangGraph Agent
    agent_graph = build_agent_graph(k8s_tools, kb, llm)
    print("✅ Agent graph compiled with LangGraph")
    
    # 6. Run MCP Server
    server = MCPServer(agent_graph, k8s_tools)
    server.run()


if __name__ == "__main__":
    main()