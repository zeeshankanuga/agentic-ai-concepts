#!/usr/bin/env python3
"""
Level 5e: Class-Based Tools with Structured Output

NEW CONCEPTS INTRODUCED:
- Tools organized as methods on a class (not loose functions)
- Dependency injection (shared clients, config via constructor)
- Structured tool results (typed dicts, not raw strings)
- Tool schemas with proper JSON Schema for LLM function calling
- Error handling with consistent result format
- Tool discovery and registration
- Analysis/logic inside tools (not just raw API calls)

ARCHITECTURE EVOLUTION:
Level 5d: LangGraph workflow with basic nodes
Level 5e (this file): Class-based tools with structured output
Level 5f: Multi-step reasoning with explicit steps
Level 6: Full system (kubernetes-agent.py) - combines all patterns
"""

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
import subprocess
import json
import asyncio
from enum import Enum


# =============================================================================
# STEP 1: DEFINE STRUCTURED RESULT TYPES
# =============================================================================

class ToolStatus(str, Enum):
    """Standardized tool execution status."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class ToolResult:
    """
    Standardized tool result structure.
    
    CONCEPT: Tools should return structured data the LLM can reason over,
    not just raw text. This includes status, data, and metadata.
    """
    status: ToolStatus
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }
    
    @classmethod
    def success(cls, data: Any, **metadata) -> "ToolResult":
        return cls(status=ToolStatus.SUCCESS, data=data, metadata=metadata)
    
    @classmethod
    def error(cls, error: str, **metadata) -> "ToolResult":
        return cls(status=ToolStatus.ERROR, error=error, metadata=metadata)
    
    @classmethod
    def partial(cls, data: Any, error: str, **metadata) -> "ToolResult":
        return cls(status=ToolStatus.PARTIAL, data=data, error=error, metadata=metadata)


# =============================================================================
# STEP 2: BASE TOOL CLASS
# =============================================================================

class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    CONCEPT: Common interface for tool discovery, schema generation,
    and execution. Enables plugin-style tool architecture.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (unique identifier)."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM."""
        pass
    
    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
    
    def to_langchain_tool(self):
        """Convert to LangChain @tool decorated function."""
        # Create a function that wraps execute
        def tool_func(**kwargs) -> Dict[str, Any]:
            result = self.execute(**kwargs)
            return result.to_dict()
        
        # Set metadata for LangChain
        tool_func.__name__ = self.name
        tool_func.__doc__ = self.description
        
        return tool(tool_func)
    
    def to_mcp_tool(self) -> Dict[str, Any]:
        """Convert to MCP tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


# =============================================================================
# STEP 3: CONCRETE TOOL IMPLEMENTATIONS
# =============================================================================

class DockerToolSet:
    """
    Docker tools organized as a class with shared dependencies.
    
    CONCEPT: Class-based tools allow:
    - Dependency injection (Docker client, config, logger)
    - Shared state (connection pools, caches)
    - Easy testing (mock the class)
    - Organized namespace (docker_tools.list_containers())
    """
    
    def __init__(self, docker_cmd: str = "docker", timeout: int = 30):
        self.docker_cmd = docker_cmd
        self.timeout = timeout
        self._tools: Dict[str, BaseTool] = {}
        self._register_tools()
    
    def _register_tools(self):
        """Register all tools in this set."""
        self._tools = {
            "list_containers": ListContainersTool(self),
            "get_container_logs": GetContainerLogsTool(self),
            "inspect_container": InspectContainerTool(self),
            "get_container_stats": GetContainerStatsTool(self),
        }
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_langchain_tools(self):
        """Get all tools as LangChain @tool functions."""
        return [t.to_langchain_tool() for t in self._tools.values()]
    
    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get all tools as MCP definitions."""
        return [t.to_mcp_tool() for t in self._tools.values()]
    
    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult.error(f"Unknown tool: {tool_name}")
        return tool.execute(**kwargs)
    
    # Shared helper method
    def _run_docker(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run docker command with consistent settings."""
        cmd = [self.docker_cmd] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )


# -----------------------------------------------------------------------------
# Individual Tool Classes
# -----------------------------------------------------------------------------

class ListContainersTool(BaseTool):
    """List all containers (running or all)."""
    
    @property
    def name(self) -> str:
        return "list_containers"
    
    @property
    def description(self) -> str:
        return "List Docker containers with status, names, and basic info. Use 'all=true' to include stopped containers."
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Include stopped containers",
                    "default": False
                },
                "format": {
                    "type": "string",
                    "description": "Output format",
                    "enum": ["table", "json", "names"],
                    "default": "table"
                }
            },
            "required": []
        }
    
    def __init__(self, docker_tools: DockerToolSet):
        self.docker = docker_tools
    
    def execute(self, all: bool = False, format: str = "table") -> ToolResult:
        args = ["ps"]
        if all:
            args.append("-a")
        
        if format == "json":
            args.extend(["--format", "json"])
        elif format == "names":
            args.extend(["--format", "{{.Names}}"])
        
        try:
            result = self.docker._run_docker(args)
            
            if result.returncode != 0:
                return ToolResult.error(f"Docker error: {result.stderr}")
            
            if format == "json" and result.stdout.strip():
                # Parse JSON lines
                containers = []
                for line in result.stdout.strip().split('\n'):
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                return ToolResult.success(
                    data={"containers": containers, "count": len(containers)},
                    format=format
                )
            else:
                return ToolResult.success(
                    data={"output": result.stdout, "count": len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0},
                    format=format
                )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Docker command timed out")
        except Exception as e:
            return ToolResult.error(str(e))


class GetContainerLogsTool(BaseTool):
    """Get logs from a container."""
    
    @property
    def name(self) -> str:
        return "get_container_logs"
    
    @property
    def description(self) -> str:
        return "Get logs from a specific container. Supports tail, follow, and time filtering."
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of lines from end",
                    "default": 50
                },
                "since": {
                    "type": "string",
                    "description": "Show logs since timestamp (e.g., '1h', '2024-01-01')"
                },
                "follow": {
                    "type": "boolean",
                    "description": "Follow log output (not supported in sync mode)",
                    "default": False
                }
            },
            "required": ["container"]
        }
    
    def __init__(self, docker_tools: DockerToolSet):
        self.docker = docker_tools
    
    def execute(self, container: str, tail: int = 50, since: Optional[str] = None, follow: bool = False) -> ToolResult:
        if follow:
            return ToolResult.error("Follow mode not supported in sync execution. Use async version.")
        
        args = ["logs", "--tail", str(tail)]
        if since:
            args.extend(["--since", since])
        args.append(container)
        
        try:
            result = self.docker._run_docker(args)
            
            if result.returncode != 0:
                return ToolResult.error(f"Docker error: {result.stderr}")
            
            return ToolResult.success(
                data={"logs": result.stdout, "container": container, "lines": len(result.stdout.split('\n'))},
                tail=tail,
                since=since
            )
        except Exception as e:
            return ToolResult.error(str(e))


class InspectContainerTool(BaseTool):
    """Get detailed container information."""
    
    @property
    def name(self) -> str:
        return "inspect_container"
    
    @property
    def description(self) -> str:
        return "Get detailed container configuration and state (like docker inspect)."
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "format": {
                    "type": "string",
                    "description": "Go template format string"
                }
            },
            "required": ["container"]
        }
    
    def __init__(self, docker_tools: DockerToolSet):
        self.docker = docker_tools
    
    def execute(self, container: str, format: Optional[str] = None) -> ToolResult:
        args = ["inspect"]
        if format:
            args.extend(["--format", format])
        args.append(container)
        
        try:
            result = self.docker._run_docker(args)
            
            if result.returncode != 0:
                return ToolResult.error(f"Docker error: {result.stderr}")
            
            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                return ToolResult.success(data=data[0] if data else {}, container=container)
            except json.JSONDecodeError:
                return ToolResult.success(data={"raw": result.stdout}, container=container)
        except Exception as e:
            return ToolResult.error(str(e))


class GetContainerStatsTool(BaseTool):
    """Get container resource usage statistics."""
    
    @property
    def name(self) -> str:
        return "get_container_stats"
    
    @property
    def description(self) -> str:
        return "Get real-time resource usage (CPU, memory, network, block I/O) for containers."
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID (optional, defaults to all)"
                },
                "no_stream": {
                    "type": "boolean",
                    "description": "Disable streaming, get single snapshot",
                    "default": True
                }
            },
            "required": []
        }
    
    def __init__(self, docker_tools: DockerToolSet):
        self.docker = docker_tools
    
    def execute(self, container: Optional[str] = None, no_stream: bool = True) -> ToolResult:
        args = ["stats"]
        if no_stream:
            args.append("--no-stream")
        if container:
            args.append(container)
        
        # Use format for parseable output
        args.extend(["--format", "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"])
        
        try:
            result = self.docker._run_docker(args)
            
            if result.returncode != 0:
                return ToolResult.error(f"Docker error: {result.stderr}")
            
            return ToolResult.success(
                data={"output": result.stdout, "container": container or "all"},
                no_stream=no_stream
            )
        except Exception as e:
            return ToolResult.error(str(e))


# =============================================================================
# STEP 4: ANALYSIS TOOLS (Tools with built-in logic)
# =============================================================================

class AnalysisToolSet:
    """
    Analysis tools that include domain logic (not just raw API calls).
    
    CONCEPT: Tools can do MORE than just call APIs. They can:
    - Analyze data and detect issues
    - Provide recommendations
    - Correlate multiple data sources
    This moves logic FROM the LLM prompt INTO the tool (more reliable).
    """
    
    def __init__(self, docker_tools: DockerToolSet):
        self.docker = docker_tools
    
    def analyze_container_health(self, container: str) -> ToolResult:
        """
        Comprehensive health analysis for a container.
        
        This tool does the analysis that would otherwise need
        multiple LLM reasoning steps.
        """
        # Get container details
        inspect_result = self.docker.execute("inspect_container", container=container)
        if inspect_result.status != ToolStatus.SUCCESS:
            return ToolResult.error(f"Cannot inspect container: {inspect_result.error}")
        
        container_data = inspect_result.data
        issues = []
        recommendations = []
        
        # Check state
        state = container_data.get("State", {})
        if state.get("Status") == "exited":
            exit_code = state.get("ExitCode", 0)
            if exit_code != 0:
                issues.append(f"Container exited with code {exit_code}")
                recommendations.append("Check logs with get_container_logs")
            if state.get("OOMKilled"):
                issues.append("Container was OOMKilled (out of memory)")
                recommendations.append("Increase memory limit or fix memory leak")
        
        # Check restarts
        restart_count = state.get("RestartCount", 0)
        if restart_count > 5:
            issues.append(f"High restart count: {restart_count}")
            recommendations.append("Investigate crash loop - check logs and resource limits")
        
        # Check health check
        health = state.get("Health", {})
        if health:
            status = health.get("Status", "unknown")
            if status == "unhealthy":
                issues.append("Health check failing")
                recommendations.append("Check health check command and application health")
        
        # Check resources
        host_config = container_data.get("HostConfig", {})
        memory_limit = host_config.get("Memory", 0)
        if memory_limit == 0:
            issues.append("No memory limit set (risk of OOM)")
            recommendations.append("Set memory limit with --memory flag")
        
        cpu_limit = host_config.get("NanoCpus", 0)
        if cpu_limit == 0:
            issues.append("No CPU limit set")
            recommendations.append("Consider setting CPU limit with --cpus flag")
        
        return ToolResult.success(
            data={
                "container": container,
                "state": state.get("Status"),
                "issues": issues,
                "recommendations": recommendations,
                "restart_count": restart_count,
                "health_status": health.get("Status") if health else "none",
                "memory_limit_bytes": memory_limit,
                "cpu_limit_nanos": cpu_limit
            },
            analysis_type="health"
        )
    
    def diagnose_common_issues(self) -> ToolResult:
        """
        Scan all containers for common issues.
        
        Returns a summary report - useful for dashboard/overview.
        """
        # Get all containers
        list_result = self.docker.execute("list_containers", all=True, format="json")
        if list_result.status != ToolStatus.SUCCESS:
            return ToolResult.error(f"Cannot list containers: {list_result.error}")
        
        containers = list_result.data.get("containers", [])
        
        summary = {
            "total": len(containers),
            "running": 0,
            "exited": 0,
            "issues_found": []
        }
        
        for c in containers:
            state = c.get("State", "")
            if state == "running":
                summary["running"] += 1
            elif state == "exited":
                summary["exited"] += 1
                exit_code = c.get("ExitCode", 0)
                if exit_code != 0:
                    summary["issues_found"].append({
                        "container": c.get("Names", "unknown"),
                        "issue": f"Exited with code {exit_code}",
                        "severity": "high"
                    })
        
        return ToolResult.success(
            data=summary,
            analysis_type="overview"
        )


# =============================================================================
# STEP 5: AGENT INTEGRATION
# =============================================================================

SYSTEM_PROMPT = """You are a Docker expert with access to structured tools.
Tools return structured data (JSON) - use the data fields directly.
Be concise. Cite tool results by name."""


class StructuredToolAgent:
    """
    Agent that uses class-based structured tools.
    
    DEMONSTRATES:
    - Tool discovery from class-based sets
    - Structured result handling
    - Analysis tools with built-in logic
    """
    
    def __init__(self, model: str = "gemma4:e4b"):
        self.model = model
        self.docker_tools = DockerToolSet()
        self.analysis_tools = AnalysisToolSet(self.docker_tools)
        self.agent = None
        self._setup_agent()
    
    def _setup_agent(self):
        """Create LangChain agent with all tools."""
        # Collect all LangChain tools
        lc_tools = []
        lc_tools.extend(self.docker_tools.get_langchain_tools())
        
        # Add analysis tools as @tool functions
        @tool
        def analyze_container_health(container: str) -> Dict[str, Any]:
            """Comprehensive health analysis for a container."""
            result = self.analysis_tools.analyze_container_health(container)
            return result.to_dict()
        
        @tool
        def diagnose_common_issues() -> Dict[str, Any]:
            """Scan all containers for common issues."""
            result = self.analysis_tools.diagnose_common_issues()
            return result.to_dict()
        
        lc_tools.extend([analyze_container_health, diagnose_common_issues])
        
        llm = ChatOllama(model=self.model, temperature=0, system=SYSTEM_PROMPT)
        self.agent = create_agent(llm, lc_tools)
    
    async def run(self, query: str) -> str:
        """Run agent on a query."""
        response = await self.agent.ainvoke({
            "messages": [HumanMessage(content=query)]
        })
        return response['messages'][-1].content


async def demo():
    """Demonstrate structured tools."""
    print("="*60)
    print("🎯 DEMO: Class-Based Structured Tools")
    print("="*60)
    
    docker_tools = DockerToolSet()
    analysis_tools = AnalysisToolSet(docker_tools)
    
    # Demo 1: List containers with structured output
    print("\n📋 List Containers (structured):")
    result = docker_tools.execute("list_containers", all=True, format="json")
    print(f"   Status: {result.status.value}")
    print(f"   Count: {result.data.get('count', 0) if result.data else 0}")
    if result.data and result.data.get('containers'):
        for c in result.data['containers'][:3]:
            print(f"   - {c.get('Names', 'unknown')}: {c.get('State', 'unknown')}")
    else:
        print(f"   Error: {result.error}")
        print("   (Docker may not be available - this is expected in demo)")
    
    # Demo 2: Health analysis
    print("\n🔍 Health Analysis (with logic):")
    list_result = docker_tools.execute("list_containers", all=True, format="json")
    if list_result.data and list_result.data.get('containers'):
        first_container = list_result.data['containers'][0].get('Names', '')
        if first_container:
            health_result = analysis_tools.analyze_container_health(first_container)
            print(f"   Container: {first_container}")
            print(f"   Issues: {health_result.data.get('issues', [])}")
            print(f"   Recommendations: {health_result.data.get('recommendations', [])}")
        else:
            print("   No containers found")
    else:
        print(f"   Error: {list_result.error}")
        print("   (Docker may not be available - this is expected in demo)")
    
    # Demo 3: Overview diagnosis
    print("\n📊 Overview Diagnosis:")
    diag_result = analysis_tools.diagnose_common_issues()
    if diag_result.data:
        print(f"   Total: {diag_result.data.get('total')}")
        print(f"   Running: {diag_result.data.get('running')}")
        print(f"   Exited: {diag_result.data.get('exited')}")
        print(f"   Issues: {diag_result.data.get('issues_found')}")
    else:
        print(f"   Error: {diag_result.error}")
        print("   (Docker may not be available - this is expected in demo)")


async def interactive():
    """Interactive agent with structured tools."""
    agent = StructuredToolAgent()
    
    print("\n" + "="*60)
    print("🤖 Structured Tools Agent (Level 5e)")
    print("   Tools: list_containers, get_container_logs, inspect_container,")
    print("          get_container_stats, analyze_container_health, diagnose_common_issues")
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
        
        try:
            answer = await agent.run(user_input)
            print(f"Agent: {answer}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await demo()
    else:
        await interactive()


if __name__ == "__main__":
    asyncio.run(main())