#!/usr/bin/env python3
"""
Level 5c: Agent with Simple In-Memory RAG (Retrieval-Augmented Generation)

NEW CONCEPTS INTRODUCED:
- Document ingestion and storage (in-memory, no external DB)
- Text chunking (splitting large docs into retrieval-sized pieces)
- Simple embedding simulation (keyword-based for learning, no heavy deps)
- Semantic search / retrieval (find relevant chunks for query)
- Context augmentation (inject retrieved docs into LLM prompt)
- Source attribution (show which docs were used)

ARCHITECTURE EVOLUTION:
Level 5b: Async agent with streaming
Level 5c (this file): RAG - Knowledge retrieval + generation
Level 5d: LangGraph workflow
Level 5e: Class-based tools
Level 5f: Multi-step reasoning
Level 6: Full system (kubernetes-agent.py) - adds vector DB, embeddings, LangGraph
"""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
import asyncio
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import math


SYSTEM_PROMPT = """
You are a Docker expert. Explain things in 1-2 lines max.
You don't overthink, hallucinate, or keep reasoning in loops.
You reason and act according to user prompt.

Your tasks:
1. Tell about errors (what went wrong)
2. Tell about root cause (likely cause)
3. Tell about the fix/solution (short)
"""


# =============================================================================
# SIMPLE IN-MEMORY RAG IMPLEMENTATION (No Vector DB Required)
# =============================================================================
# This demonstrates RAG concepts WITHOUT requiring:
# - chromadb, sentence-transformers, huggingface, etc.
# Uses simple keyword overlap scoring for educational clarity.

@dataclass
class Document:
    """A document in our knowledge base."""
    id: str
    title: str
    content: str
    source: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[str] = field(default_factory=list)


@dataclass 
class RetrievalResult:
    """Result of a retrieval operation."""
    document: Document
    chunk: str
    score: float
    chunk_index: int


class SimpleTextSplitter:
    """
    Split text into overlapping chunks for retrieval.
    
    CONCEPT: Large documents don't fit in context window and dilute embeddings.
    Chunking creates focused pieces that retrieve precisely.
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the chunk boundary
                for sep in ['. ', '\n\n', '\n', ' ']:
                    pos = text.rfind(sep, start, end)
                    if pos != -1:
                        end = pos + len(sep)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks


class SimpleEmbeddingSimulator:
    """
    Simulate embeddings using keyword overlap (TF-IDF style).
    
    CONCEPT: Real embeddings convert text to vectors (384+ dimensions).
    This simulates the CONCEPT for learning without heavy dependencies.
    In production, use: sentence-transformers, OpenAI embeddings, etc.
    """
    
    def __init__(self):
        self.doc_freq = defaultdict(int)  # word -> how many docs contain it
        self.total_docs = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric."""
        return re.findall(r'\b\w+\b', text.lower())
    
    def fit(self, documents: List[Document]):
        """Build vocabulary statistics from documents."""
        self.total_docs = len(documents)
        self.doc_freq.clear()
        
        for doc in documents:
            # Get unique words in this document
            words = set(self._tokenize(doc.content))
            for word in words:
                self.doc_freq[word] += 1
    
    def score(self, query: str, text: str) -> float:
        """
        Score relevance using TF-IDF style keyword overlap.
        Higher = more relevant.
        """
        query_words = set(self._tokenize(query))
        text_words = self._tokenize(text)
        text_word_set = set(text_words)
        
        if not query_words or not text_word_set:
            return 0.0
        
        # TF-IDF style scoring
        score = 0.0
        for word in query_words:
            if word in text_word_set:
                # Term frequency in text
                tf = text_words.count(word) / len(text_words)
                # Inverse document frequency
                df = self.doc_freq.get(word, 1)
                idf = math.log(self.total_docs / df) if df > 0 else 0
                score += tf * idf
        
        # Normalize by query length
        return score / len(query_words)


class InMemoryKnowledgeBase:
    """
    In-memory RAG knowledge base.
    
    DEMONSTRATES THESE RAG CONCEPTS:
    1. Document ingestion (add_knowledge)
    2. Chunking (split into retrieval-sized pieces)
    3. Indexing (build search structures)
    4. Retrieval (search for relevant chunks)
    5. Augmentation (inject into prompt)
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.documents: Dict[str, Document] = {}
        self.splitter = SimpleTextSplitter(chunk_size, chunk_overlap)
        self.embedder = SimpleEmbeddingSimulator()
        self._indexed = False
    
    def add_document(self, doc_id: str, title: str, content: str, source: str = "manual", **metadata):
        """Add a document to the knowledge base."""
        doc = Document(
            id=doc_id,
            title=title,
            content=content,
            source=source,
            metadata=metadata
        )
        # Chunk the document
        doc.chunks = self.splitter.split_text(content)
        self.documents[doc_id] = doc
        self._indexed = False  # Mark for re-indexing
        print(f"📄 Added document: {title} ({len(doc.chunks)} chunks)")
    
    def add_knowledge(self, knowledge_items: List[Dict[str, str]]):
        """Bulk add knowledge from list of dicts."""
        for item in knowledge_items:
            self.add_document(
                doc_id=item.get("id", f"doc_{len(self.documents)}"),
                title=item.get("title", "Untitled"),
                content=item.get("content", ""),
                source=item.get("source", "manual"),
                topic=item.get("topic", "general")
            )
        self._build_index()
    
    def _build_index(self):
        """Build search index (fit embedder on all documents)."""
        if self.documents:
            self.embedder.fit(list(self.documents.values()))
            self._indexed = True
            print(f"🔍 Index built: {len(self.documents)} documents, "
                  f"{sum(len(d.chunks) for d in self.documents.values())} chunks")
    
    def search(self, query: str, k: int = 3) -> List[RetrievalResult]:
        """
        Retrieve top-k relevant chunks for a query.
        
        THIS IS THE CORE RAG RETRIEVAL STEP!
        """
        if not self._indexed:
            self._build_index()
        
        if not self.documents:
            return []
        
        results = []
        
        for doc in self.documents.values():
            for i, chunk in enumerate(doc.chunks):
                score = self.embedder.score(query, chunk)
                if score > 0:
                    results.append(RetrievalResult(
                        document=doc,
                        chunk=chunk,
                        score=score,
                        chunk_index=i
                    ))
        
        # Sort by score descending, take top-k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]
    
    def get_context_for_prompt(self, query: str, k: int = 3) -> str:
        """
        Get formatted context string for LLM prompt augmentation.
        """
        results = self.search(query, k)
        
        if not results:
            return "No relevant knowledge found."
        
        context_parts = ["=== RETRIEVED KNOWLEDGE ==="]
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"\n[{i}] Source: {result.document.title} "
                f"(chunk {result.chunk_index + 1}/{len(result.document.chunks)}, "
                f"score: {result.score:.3f})"
                f"\n{result.chunk}"
            )
        
        context_parts.append("\n=== END RETRIEVED KNOWLEDGE ===")
        return "\n".join(context_parts)


# =============================================================================
# SAMPLE KNOWLEDGE BASE - Docker/Kubernetes Troubleshooting
# =============================================================================

DOCKER_KNOWLEDGE = [
    {
        "id": "docker-basics",
        "title": "Docker Container Lifecycle",
        "content": """
Docker Container Lifecycle Phases:
- Created: Container created but not started (docker create)
- Running: Container is executing (docker start/run)
- Paused: Processes frozen (docker pause)
- Stopped: Container exited gracefully (docker stop)
- Exited: Container stopped with exit code (docker run --rm)
- Dead: Failed to stop properly, needs cleanup

Key Commands:
- docker ps: List running containers
- docker ps -a: List all containers (including stopped)
- docker start <container>: Start stopped container
- docker stop <container>: Graceful stop (SIGTERM then SIGKILL)
- docker kill <container>: Force stop (SIGKILL)
- docker restart <container>: Stop then start
- docker rm <container>: Remove stopped container
""",
        "source": "docker-docs",
        "topic": "lifecycle"
    },
    {
        "id": "docker-common-issues",
        "title": "Common Docker Issues and Fixes",
        "content": """
Common Docker Issues:

1. Container Exits Immediately
   Cause: Main process finishes (e.g., script completes, no foreground process)
   Fix: Use CMD/ENTRYPOINT that runs in foreground, or run with -it for interactive

2. Port Already Allocated / Bind Failed
   Cause: Another container or process using the port
   Fix: docker ps to find conflicting container, stop it, or use different port (-p 8081:80)

3. Image Pull Errors (ImagePullBackOff / ErrImagePull)
   Cause: Wrong image name/tag, private registry without auth, rate limits
   Fix: Verify image name, docker login for private registries, check rate limits

4. Permission Denied / Volume Mount Issues
   Cause: SELinux, AppArmor, or file permissions on host
   Fix: Use :Z or :z suffix for volumes, check host permissions, run with --privileged if needed

5. Out of Disk Space
   Cause: Unused images, containers, volumes, build cache
   Fix: docker system prune -a, docker image prune, docker volume prune

6. Container Restarting (Restart Loop)
   Cause: Application crashes, health check fails, OOM kill
   Fix: Check logs (docker logs), check docker inspect for OOMKilled, fix app or increase memory

7. Network Issues (Cannot Connect to Container)
   Cause: Wrong network, firewall, container not exposing port
   Fix: Check docker network ls, docker inspect for IP, verify EXPOSE in Dockerfile, use --network host
""",
        "source": "docker-troubleshooting",
        "topic": "issues"
    },
    {
        "id": "docker-logs-debugging",
        "title": "Docker Logging and Debugging",
        "content": """
Docker Logging and Debugging Commands:

1. View Logs
   docker logs <container>           # All logs
   docker logs -f <container>        # Follow (tail -f)
   docker logs --tail 100 <container> # Last 100 lines
   docker logs --since 1h <container> # Last hour
   docker logs -t <container>        # With timestamps

2. Inspect Container
   docker inspect <container>        # Full JSON config/state
   docker inspect --format '{{.State.Status}}' <container>  # Just status
   docker top <container>            # Running processes inside

3. Execute Commands in Container
   docker exec -it <container> sh    # Interactive shell
   docker exec <container> cmd       # Run single command

4. Resource Usage
   docker stats <container>          # Live CPU/memory/network
   docker stats --no-stream          # One-time snapshot

5. Events (Real-time)
   docker events                     # Stream all daemon events
   docker events --filter container=<name>  # Filter by container

6. Debug Image Layers
   docker history <image>            # Show image layers
   docker image inspect <image>      # Full image metadata
""",
        "source": "docker-docs",
        "topic": "debugging"
    },
    {
        "id": "docker-compose-basics",
        "title": "Docker Compose Basics",
        "content": """
Docker Compose Key Concepts:

1. docker-compose.yml Structure:
   version: '3.8'
   services:
     web:
       image: nginx:latest
       ports: ["80:80"]
       volumes: ["./html:/usr/share/nginx/html"]
       environment: [ENV_VAR=value]
       depends_on: [db]
     db:
       image: postgres:15
       environment: [POSTGRES_PASSWORD=secret]

2. Common Commands:
   docker compose up -d        # Start in background
   docker compose down         # Stop and remove
   docker compose ps           # List services
   docker compose logs -f      # Follow logs
   docker compose exec web sh  # Exec in service
   docker compose build        # Build images
   docker compose pull         # Pull latest images

3. Networking:
   - Services communicate by service name (web -> db)
   - Default network created per project
   - Ports only exposed to host if explicitly mapped

4. Volumes:
   - Named volumes persist data (db-data:/var/lib/postgresql/data)
   - Bind mounts for development (./code:/app)
   - Use :ro for read-only mounts
""",
        "source": "docker-compose-docs",
        "topic": "compose"
    }
]


# =============================================================================
# RAG-ENABLED AGENT
# =============================================================================

class RAGAgent:
    """
    Agent with Retrieval-Augmented Generation.
    
    FLOW:
    1. User asks question
    2. Retrieve relevant knowledge from KB
    3. Augment prompt with retrieved context
    4. LLM generates answer using knowledge + tools
    5. Return answer with source citations
    """
    
    def __init__(self, model: str = "gemma4:e4b"):
        self.model = model
        self.knowledge_base = InMemoryKnowledgeBase(chunk_size=400, chunk_overlap=50)
        self.client = None
        self.agent = None
        self.messages = []
    
    async def initialize(self):
        """Initialize MCP tools and load knowledge base."""
        print("🔌 Connecting to MCP server...")
        self.client = MultiServerMCPClient({
            "docker-mcp": {
                "transport": "stdio",
                "command": "python3",
                "args": ["03-mcp_server.py"]
            }
        })
        
        tools = await self.client.get_tools()
        print(f"✓ Discovered {len(tools)} MCP tools")
        
        # Load knowledge base
        print("\n📚 Loading knowledge base...")
        self.knowledge_base.add_knowledge(DOCKER_KNOWLEDGE)
        
        # Create agent
        llm = ChatOllama(
            model=self.model,
            temperature=0.8,
            system=SYSTEM_PROMPT
        )
        self.agent = create_agent(llm, tools)
        
        # Initialize conversation with system prompt
        self.messages = [SystemMessage(content=SYSTEM_PROMPT)]
    
    def _build_augmented_prompt(self, user_query: str) -> str:
        """
        Build prompt with retrieved knowledge context.
        This is the 'A' in RAG - Augmentation!
        """
        context = self.knowledge_base.get_context_for_prompt(user_query, k=3)
        
        augmented = f"""{context}

USER QUESTION: {user_query}

INSTRUCTIONS:
1. Use the retrieved knowledge above to inform your answer
2. If knowledge is relevant, cite it like [Source: Title]
3. Also use available MCP tools for live Docker info
4. Be concise (1-2 lines per point)"""
        
        return augmented
    
    async def process_query(self, user_query: str) -> str:
        """Process a query with RAG augmentation."""
        # Build augmented prompt
        augmented_prompt = self._build_augmented_prompt(user_query)
        
        # Add to conversation
        self.messages.append(HumanMessage(content=augmented_prompt))
        
        # Context window management
        MAX_MSGS = 20
        if len(self.messages) > MAX_MSGS:
            self.messages = [self.messages[0]] + self.messages[-(MAX_MSGS - 1):]
        
        # Get response from agent
        response = await self.agent.ainvoke({"messages": self.messages})
        assistant_msg = response['messages'][-1]
        
        # Add to history
        self.messages.append(assistant_msg)
        
        return assistant_msg.content
    
    async def close(self):
        if self.client and hasattr(self.client, 'close'):
            await self.client.close()


async def interactive_mode():
    """Run interactive RAG agent."""
    agent = RAGAgent()
    await agent.initialize()
    
    print("\n" + "="*60)
    print("🤖 RAG-Enabled Docker Agent (Level 5c)")
    print("   Knowledge: Docker lifecycle, issues, debugging, compose")
    print("   Commands: 'exit', 'clear', 'search <query>', 'kb'")
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
            agent.messages = [SystemMessage(content=SYSTEM_PROMPT)]
            print("🧹 Memory cleared!\n")
            continue
        
        if user_input.lower() == "kb":
            print(f"\n📚 Knowledge Base: {len(agent.knowledge_base.documents)} documents")
            for doc in agent.knowledge_base.documents.values():
                print(f"  - {doc.title} ({len(doc.chunks)} chunks)")
            print()
            continue
        
        if user_input.lower().startswith("search "):
            query = user_input[7:].strip()
            results = agent.knowledge_base.search(query, k=3)
            print(f"\n🔍 Search results for: {query}")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.document.title} (score: {r.score:.3f})")
                print(f"     {r.chunk[:100]}...")
            print()
            continue
        
        try:
            answer = await agent.process_query(user_input)
            print(f"Agent: {answer}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    await agent.close()


async def demo_rag():
    """Demonstrate RAG retrieval without full agent."""
    print("\n" + "="*60)
    print("🎯 DEMO: RAG Retrieval")
    print("="*60)
    
    kb = InMemoryKnowledgeBase()
    kb.add_knowledge(DOCKER_KNOWLEDGE)
    
    test_queries = [
        "container exits immediately",
        "port already allocated",
        "how to view logs",
        "docker compose up",
        "out of disk space"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        results = kb.search(query, k=2)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.document.title} (score: {r.score:.3f})")
            print(f"     {r.chunk[:150]}...")


async def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await demo_rag()
        return
    
    await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())