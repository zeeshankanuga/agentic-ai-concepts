# Kubernetes Learning Agent - Agentic AI Demo

An educational implementation demonstrating **core Agentic AI concepts** with a practical Kubernetes troubleshooting agent.

## 🎯 Learning Objectives

This project teaches you how Agentic AI works end-to-end:

| Concept | Implementation | File Location |
|---------|---------------|---------------|
| **Input Processing** | User prompt → Query rewriting | `rewrite_query()` node |
| **Embedding** | Text → Vectors (MiniLM) | `HuggingFaceEmbeddings` |
| **Chunking** | Split docs → Overlapping chunks | `RecursiveCharacterTextSplitter` |
| **Vector DB** | Store/retrieve semantic knowledge | `ChromaDB` |
| **RAG Retrieval** | Query → Similar docs | `knowledge_base.search()` |
| **LLM Calling** | Local (Ollama) or Cloud (OpenAI) | `create_llm()` |
| **Tool Use** | LLM decides → Execute MCP tools | `decide_action()` + `execute_tools()` |
| **LangGraph** | Orchestrate multi-step workflow | `StateGraph` with 5 nodes |
| **MCP Protocol** | JSON-RPC over stdio | `MCPServer` class |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC AI WORKFLOW (LangGraph)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │ 1. REWRITE   │───▶│ 2. RETRIEVE  │───▶│ 3. DECIDE    │───▶│ 4. EXEC  │  │
│  │    QUERY     │    │  (Vector DB) │    │  (LLM)       │    │  TOOLS   │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘    └────┬─────┘  │
│                                                  │                 │        │
│                                                  ▼                 ▼        │
│                                           ┌──────────────┐    ┌──────────┐  │
│                                           │ 5. SYNTHESIZE│◀───│  TOOL    │  │
│                                           │   (LLM)      │    │ RESULTS  │  │
│                                           └──────┬───────┘    └──────────┘  │
│                                                  │                          │
│                                                  ▼                          │
│                                           ┌──────────────┐                 │
│                                           │ FINAL ANSWER │                 │
│                                           └──────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP SERVER (stdio)                                │
│  JSON-RPC 2.0 ◀──────────────────────────────────────▶ LLM Client          │
│  (Claude, Custom Agent, etc.)                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      KUBERNETES CLUSTER (KIND)                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                                     │
│  │ Pods    │  │ Deploy  │  │ Services│  ← 3 Tools: list_pods, get_logs,   │
│  │ Logs    │  │ ments   │  │ Events  │     analyze_pod                    │
│  └─────────┘  └─────────┘  └─────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

| Tool | Version | Install Command |
|------|---------|-----------------|
| **Docker** | 24+ | `brew install docker` / [docker.com](https://docker.com) |
| **KIND** | 0.22+ | `brew install kind` / `go install sigs.k8s.io/kind@latest` |
| **kubectl** | 1.28+ | `brew install kubectl` |
| **Python** | 3.10+ | `brew install python` |
| **Ollama** | Latest | `brew install ollama` / [ollama.com](https://ollama.com) |

---

## 🚀 Step-by-Step Deployment to KIND

### Step 1: Create KIND Cluster

```bash
# Create a KIND cluster with extra port mappings for MCP access
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 11434  # Ollama port (if running in cluster)
    hostPort: 11434
    protocol: TCP
EOF

kind create cluster --name k8s-agent-demo --config kind-config.yaml

# Verify cluster
kubectl cluster-info --context kind-k8s-agent-demo
kubectl get nodes
```

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install kubernetes langchain langgraph langchain-chroma langchain-huggingface langchain-ollama chromadb sentence-transformers

# Verify imports work
python3 -c "
import kubernetes, langchain, langgraph, chromadb, sentence_transformers
print('✅ All dependencies installed')
"
```

### Step 3: Start Ollama (Local LLM)

```bash
# Start Ollama server (in background)
ollama serve &

# Wait a moment, then pull a model
sleep 3
ollama pull llama3.1

# Test it works
ollama run llama3.1 "Hello, respond in one sentence."
```

> **Alternative**: Use OpenAI instead by setting `export OPENAI_API_KEY=sk-...` and installing `langchain-openai`

### Step 4: Prepare the Agent Files

```bash
# Navigate to agent directory
cd /Users/zeeshankanuga/Zeeshan/DevOps/agentic-ai/demo/agent

# Verify files exist
ls -la kubernetes-agent.py README.md
```

### Step 5: Run Agent Locally (Test First)

```bash
# Test the agent runs without errors (will wait for stdin)
timeout 5 python3 kubernetes-agent.py <<< '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# Should output JSON-RPC response with server info
```

### Step 6: Deploy Agent to KIND as a Pod

#### 6a: Build Docker Image

```dockerfile
# Dockerfile (create this in agent directory)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY kubernetes-agent.py .

# Run as non-root (K8s best practice)
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import kubernetes; print('ok')" || exit 1

ENTRYPOINT ["python3", "kubernetes-agent.py"]
```

```bash
# Create requirements.txt
cat <<EOF > requirements.txt
kubernetes==30.0.0
langchain==0.2.0
langgraph==0.2.0
langchain-chroma==0.1.0
langchain-huggingface==0.1.0
langchain-ollama==0.1.0
chromadb==0.5.0
sentence-transformers==3.0.0
EOF

# Build image
docker build -t k8s-learning-agent:latest .

# Load into KIND cluster (required for KIND)
kind load docker-image k8s-learning-agent:latest --name k8s-agent-demo
```

#### 6b: Create RBAC for Agent

```yaml
# rbac.yaml - Permissions for the agent to read K8s resources
apiVersion: v1
kind: ServiceAccount
metadata:
  name: k8s-agent
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-agent-reader
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "pods/exec", "services", "endpoints", "events", "configmaps", "namespaces", "nodes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses", "networkpolicies"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["metrics.k8s.io"]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: k8s-agent-binding
subjects:
- kind: ServiceAccount
  name: k8s-agent
  namespace: default
roleRef:
  kind: ClusterRole
  name: k8s-agent-reader
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f rbac.yaml
```

#### 6c: Deploy Agent Pod

```yaml
# agent-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: k8s-learning-agent
  namespace: default
  labels:
    app: k8s-learning-agent
spec:
  serviceAccountName: k8s-agent
  containers:
  - name: agent
    image: k8s-learning-agent:latest
    imagePullPolicy: Never  # Critical for KIND local image
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "1000m"
    env:
    - name: PYTHONUNBUFFERED
      value: "1"
  restartPolicy: OnFailure
```

```bash
kubectl apply -f agent-pod.yaml

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/k8s-learning-agent --timeout=60s

# Check logs
kubectl logs k8s-learning-agent
```

### Step 7: Test Agent from Inside Cluster

```bash
# Exec into the agent pod and test MCP communication
kubectl exec -i k8s-learning-agent -- python3 -c "
import json, sys
# Send initialize request
print(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}}), flush=True)
" | head -20
```

### Step 8: Connect from Your Machine (Port Forward)

Since MCP uses stdio, we need a bridge. Create a simple client:

```python
# test_client.py - Run on your LOCAL machine
import json
import subprocess
import sys

def test_agent():
    # Use kubectl exec as transport to talk to agent in cluster
    proc = subprocess.Popen(
        ["kubectl", "exec", "-i", "k8s-learning-agent", "--", "python3", "kubernetes-agent.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 1. Initialize
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    print("Initialize:", json.dumps(resp, indent=2))
    
    # 2. List tools
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    print("\nTools:", json.dumps(resp, indent=2))
    
    # 3. Call tool via agent (natural language)
    req = {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "list_pods", "arguments": {"namespace": "default"}}
    }
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    print("\nList Pods Result:", json.dumps(resp, indent=2))
    
    proc.terminate()

if __name__ == "__main__":
    test_agent()
```

```bash
python3 test_client.py
```

---

## 🧪 Testing the Agent

### Test 1: List Pods
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_pods","arguments":{"namespace":"default"}}}
```

### Test 2: Analyze a Problematic Pod

First, create a failing pod:
```bash
kubectl run crash-loop --image=busybox --restart=Always -- /bin/sh -c "exit 1"
```

Then analyze:
```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze_pod","arguments":{"pod_name":"crash-loop","namespace":"default"}}}
```

### Test 3: Get Logs
```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_pod_logs","arguments":{"pod_name":"crash-loop","namespace":"default","tail_lines":20}}}
```

### Test 4: Natural Language Query (Full Agent)
```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_pods","arguments":{"namespace":"kube-system"}}}
```
The agent will:
1. Rewrite query → "Kubernetes troubleshooting: list pods in kube-system"
2. Retrieve → Search vector DB for relevant K8s knowledge
3. Decide → LLM chooses `list_pods` tool
4. Execute → Run tool on cluster
5. Synthesize → Return formatted answer with context

---

## 📚 Understanding the Code

### Key Files

```
agent/
├── kubernetes-agent.py   # Complete agent (single file for learning)
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container image
├── rbac.yaml           # K8s permissions
├── agent-pod.yaml      # Pod deployment
├── kind-config.yaml    # KIND cluster config
└── test_client.py      # Test script
```

### Core Classes

| Class | Purpose | Key Methods |
|-------|---------|-------------|
| `KubernetesManager` | K8s connection | `initialize()`, `is_ready()` |
| `KnowledgeBase` | Vector DB + Embeddings | `add_knowledge()`, `search()` |
| `KubernetesTools` | 3 MCP Tools | `list_pods()`, `get_pod_logs()`, `analyze_pod()` |
| `MCPServer` | JSON-RPC Server | `handle_request()`, `run()` |
| `AgentState` | LangGraph State | TypedDict with 7 fields |

### LangGraph Nodes Explained

```python
# 1. REWRITE QUERY - Optimize for retrieval
def rewrite_query(state):
    # "Why is my pod crashing?" → "Kubernetes troubleshooting: pod crashing CrashLoopBackOff"

# 2. RETRIEVE - Semantic search in ChromaDB
def retrieve(state):
    # Embed query → Find similar vectors → Return top 3 chunks

# 3. DECIDE ACTION - LLM reasoning
def decide_action(state):
    # LLM sees: context + tools + query
    # Returns: {"action": "tool_call", "tool": "analyze_pod", "args": {...}}

# 4. EXECUTE TOOLS - Run on real cluster
def execute_tools(state):
    # Call Kubernetes API → Return structured results

# 5. SYNTHESIZE - Final answer
def synthesize(state):
    # Combine tool results + knowledge → Human-readable answer
```

---

## 🔧 Customization Guide

### Add More Tools

```python
# In KubernetesTools class
def get_events(self, namespace: str = "default") -> Dict:
    """Get recent Kubernetes events."""
    events = self.k8s.core_v1.list_namespaced_event(namespace=namespace)
    return {"events": [{"type": e.type, "reason": e.reason, "message": e.message} for e in events.items]}

# Add to get_tool_definitions():
MCPTool(
    name="get_events",
    description="Get recent Kubernetes events in a namespace",
    input_schema={"type": "object", "properties": {"namespace": {"type": "string", "default": "default"}}, "required": []}
)
```

### Add More Knowledge to Vector DB

```python
# In setup_knowledge_base()
knowledge_docs.append({
    "source": "my-runbooks",
    "topic": "database-troubleshooting",
    "content": """PostgreSQL Troubleshooting:
- Connection refused: Check service, port, network policy
- Slow queries: Check pg_stat_statements, add indexes
- Lock contention: Check pg_locks, long transactions"""
})
```

### Use Different LLM

```python
# In create_llm()
# For OpenAI:
export OPENAI_API_KEY=sk-...
# For other Ollama models:
return ChatOllama(model="qwen2.5:7b", temperature=0)
# For Anthropic:
from langchain_anthropic import ChatAnthropic
return ChatAnthropic(model="claude-3-haiku-20240307")
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImagePullBackOff` for agent pod | Run `kind load docker-image k8s-learning-agent:latest --name k8s-agent-demo` |
| `Permission denied` on K8s API | Check RBAC: `kubectl auth can-i get pods --as=system:serviceaccount:default:k8s-agent` |
| `ModuleNotFoundError: langchain` | Install in venv: `pip install -r requirements.txt` |
| Ollama connection failed | Ensure `ollama serve` running, check `curl http://localhost:11434/api/tags` |
| Vector DB empty | Run `setup_knowledge_base(kb)` on startup (already in main) |
| Agent returns mock responses | Install Ollama + pull model, or set `OPENAI_API_KEY` |

---

## 📖 Learning Resources

### Agentic AI Concepts
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [RAG Pattern](https://www.pinecone.io/learn/retrieval-augmented-generation/)

### Kubernetes Debugging
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Troubleshooting Guide](https://kubernetes.io/docs/tasks/debug/debug-application/)

### Vector Databases
- [ChromaDB Docs](https://docs.trychroma.com/)
- [Embeddings Guide](https://www.sbert.net/)
- [Chunking Strategies](https://python.langchain.com/docs/modules/data_connection/document_transformers/)

---

## 🎓 Next Steps for Learning

1. **Add Memory**: Implement conversation history in `AgentState`
2. **Add Planning**: Multi-step tool calls for complex tasks
3. **Add Evaluation**: Score answer quality, retry on low confidence
4. **Add Human-in-the-loop**: Ask for confirmation before destructive actions
5. **Scale Up**: Deploy as Deployment with multiple replicas
6. **Add Metrics**: Prometheus metrics for tool usage, latency, errors

---

## 📄 License

MIT License - Educational use encouraged!

---

**Built for learning Agentic AI with real Kubernetes integration** 🚀