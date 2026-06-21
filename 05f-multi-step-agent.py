#!/usr/bin/env python3
"""
Level 5f: Multi-Step Reasoning Agent with Explicit Steps

NEW CONCEPTS INTRODUCED:
- Explicit multi-step reasoning (Plan → Execute → Reflect → Refine)
- Step-by-step execution with visible reasoning trace
- Self-correction / reflection loops
- Plan-and-execute pattern (separate planning from execution)
- Chain-of-thought with tool use at each step
- Iterative refinement based on tool results

ARCHITECTURE EVOLUTION:
Level 5e: Class-based tools with structured output
Level 5f (this file): Multi-step reasoning with explicit steps
Level 6: Full system (kubernetes-agent.py) - combines all patterns
"""

from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import subprocess


# =============================================================================
# STEP 1: DEFINE REASONING STEP TYPES
# =============================================================================

class StepType(str, Enum):
    """Types of reasoning steps."""
    PLAN = "plan"                    # Create a plan
    THINK = "think"                  # Reason about current state
    ACT = "act"                      # Execute a tool
    OBSERVE = "observe"              # Process tool result
    REFLECT = "reflect"              # Evaluate progress
    SYNTHESIZE = "synthesize"        # Produce final answer


@dataclass
class ReasoningStep:
    """A single step in the reasoning trace."""
    step_number: int
    step_type: StepType
    content: str                      # What the agent thought/did
    tool_name: Optional[str] = None   # If ACT step
    tool_args: Optional[Dict] = None  # If ACT step
    tool_result: Optional[Dict] = None # If OBSERVE step
    confidence: float = 1.0           # Agent's confidence in this step


@dataclass
class AgentPlan:
    """A multi-step plan created by the agent."""
    goal: str
    steps: List[str]                  # High-level step descriptions
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)


# =============================================================================
# STEP 2: TOOLS (Simple Docker Tools)
# =============================================================================

@tool
def list_containers(all: bool = False) -> Dict[str, Any]:
    """List Docker containers."""
    args = ["docker", "ps"]
    if all:
        args.append("-a")
    args.extend(["--format", "json"])
    
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": result.stderr}
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    containers.append(json.loads(line))
                except:
                    pass
        return {"containers": containers, "count": len(containers)}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_container_logs(container: str, tail: int = 50) -> Dict[str, Any]:
    """Get logs from a container."""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"error": result.stderr}
        return {"logs": result.stdout, "container": container}
    except Exception as e:
        return {"error": str(e)}


@tool
def inspect_container(container: str) -> Dict[str, Any]:
    """Get detailed container info."""
    try:
        result = subprocess.run(
            ["docker", "inspect", container],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"error": result.stderr}
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# STEP 3: MULTI-STEP REASONING AGENT
# =============================================================================

SYSTEM_PROMPT = """You are a Docker expert. Use multi-step reasoning:
1. PLAN: Break down the problem into steps
2. THINK: Reason about what you know
3. ACT: Use tools to gather info
4. OBSERVE: Process tool results
5. REFLECT: Evaluate if plan is working
6. SYNTHESIZE: Produce final answer

Be explicit about each step type. Show your reasoning."""


class MultiStepAgent:
    """
    Agent that performs explicit multi-step reasoning.
    
    KEY CONCEPTS:
    - Plan-and-execute: Separate planning from execution
    - Visible reasoning trace: Every step is recorded
    - Reflection: Agent evaluates progress and adjusts
    - Iterative refinement: Can loop back and retry
    """
    
    def __init__(self, model: str = "gemma4:e4b", max_steps: int = 10):
        self.model = model
        self.max_steps = max_steps
        self.llm = ChatOllama(model=model, temperature=0, system=SYSTEM_PROMPT)
        self.tools = {
            "list_containers": list_containers,
            "get_container_logs": get_container_logs,
            "inspect_container": inspect_container,
        }
        self.reasoning_trace: List[ReasoningStep] = []
        self.step_counter = 0
    
    def _add_step(self, step_type: StepType, content: str, **kwargs) -> ReasoningStep:
        """Add a step to the reasoning trace."""
        self.step_counter += 1
        step = ReasoningStep(
            step_number=self.step_counter,
            step_type=step_type,
            content=content,
            **kwargs
        )
        self.reasoning_trace.append(step)
        return step
    
    def _get_trace_summary(self) -> str:
        """Get formatted reasoning trace for prompt."""
        lines = ["REASONING TRACE:"]
        for step in self.reasoning_trace:
            prefix = f"  Step {step.step_number} [{step.step_type.value.upper()}]"
            lines.append(f"{prefix}: {step.content}")
            if step.tool_name:
                lines.append(f"    Tool: {step.tool_name}({step.tool_args})")
            if step.tool_result:
                result_str = json.dumps(step.tool_result)[:200]
                lines.append(f"    Result: {result_str}...")
        return "\n".join(lines)
    
    async def plan(self, query: str) -> AgentPlan:
        """Create a multi-step plan for the query."""
        prompt = f"""Create a step-by-step plan to answer this Docker question.

QUESTION: {query}

AVAILABLE TOOLS:
- list_containers(all?: boolean) - List containers
- get_container_logs(container: string, tail?: integer) - Get container logs
- inspect_container(container: string) - Get detailed container info

Create a plan with 2-5 high-level steps. Each step should be one action.
Respond with JSON:
{{
  "goal": "what we're trying to achieve",
  "steps": ["step 1 description", "step 2 description", ...]
}}"""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        try:
            plan_data = json.loads(response.content)
            plan = AgentPlan(
                goal=plan_data["goal"],
                steps=plan_data["steps"]
            )
            
            self._add_step(StepType.PLAN, f"Created plan: {plan.goal}")
            for i, step_desc in enumerate(plan.steps):
                self._add_step(StepType.THINK, f"Planned step {i+1}: {step_desc}")
            
            return plan
        except Exception as e:
            # Fallback plan
            return AgentPlan(
                goal=query,
                steps=["Gather container information", "Analyze and answer"]
            )
    
    async def execute_step(self, plan: AgentPlan, step_index: int, query: str) -> bool:
        """Execute a single plan step with reasoning."""
        if step_index >= len(plan.steps):
            return False
        
        step_desc = plan.steps[step_index]
        
        # Think about this step
        think_prompt = f"""We're executing step {step_index + 1} of {len(plan.steps)}: {step_desc}

Original question: {query}
Plan goal: {plan.goal}
Completed steps: {plan.completed_steps}

Reasoning trace so far:
{self._get_trace_summary()}

What should we do for this step? Decide:
1. If we need a tool, specify which and with what args
2. If we can reason directly, provide the reasoning

Respond with JSON:
{{
  "action": "tool" | "reason",
  "tool": "tool_name_if_tool",
  "args": {{"param": "value"}},
  "reasoning": "why this action"
}}"""
        
        response = await self.llm.ainvoke([HumanMessage(content=think_prompt)])
        
        try:
            decision = json.loads(response.content)
        except:
            decision = {"action": "reason", "reasoning": "Continue with plan"}
        
        if decision["action"] == "tool":
            tool_name = decision["tool"]
            tool_args = decision.get("args", {})
            
            self._add_step(StepType.ACT, decision["reasoning"], 
                          tool_name=tool_name, tool_args=tool_args)
            
            # Execute tool
            if tool_name in self.tools:
                tool_func = self.tools[tool_name]
                result = tool_func.invoke(tool_args)
                
                self._add_step(StepType.OBSERVE, f"Tool returned result", 
                              tool_result=result)
            else:
                error_result = {"error": f"Unknown tool: {tool_name}"}
                self._add_step(StepType.OBSERVE, f"Tool error", 
                              tool_result=error_result)
        else:
            self._add_step(StepType.THINK, decision["reasoning"])
        
        plan.completed_steps.append(step_desc)
        plan.current_step = step_index + 1
        return True
    
    async def reflect(self, plan: AgentPlan, query: str) -> bool:
        """Reflect on progress and decide if plan needs adjustment."""
        if len(self.reasoning_trace) < 2:
            return True  # Continue
        
        prompt = f"""Reflect on progress so far.

Original question: {query}
Plan goal: {plan.goal}
Plan steps: {plan.steps}
Completed: {plan.completed_steps}
Current step: {plan.current_step}/{len(plan.steps)}

Reasoning trace:
{self._get_trace_summary()}

Have we gathered enough information to answer the question?
Should we continue the plan, add a step, or are we done?

Respond with JSON:
{{
  "continue": true/false,
  "add_step": "optional new step description",
  "reasoning": "why"
}}"""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        try:
            reflection = json.loads(response.content)
            self._add_step(StepType.REFLECT, reflection["reasoning"])
            
            if reflection.get("add_step"):
                plan.steps.append(reflection["add_step"])
                self._add_step(StepType.PLAN, f"Added step: {reflection['add_step']}")
            
            return reflection.get("continue", True)
        except:
            return True
    
    async def synthesize(self, query: str) -> str:
        """Produce final answer from all gathered information."""
        prompt = f"""Synthesize a final answer based on all reasoning and tool results.

Original question: {query}

Full reasoning trace:
{self._get_trace_summary()}

Provide a clear, concise answer (2-4 bullet points). Cite specific tool results."""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        self._add_step(StepType.SYNTHESIZE, "Generated final answer")
        return response.content
    
    async def run(self, query: str) -> Dict[str, Any]:
        """Run full multi-step reasoning process."""
        self.reasoning_trace = []
        self.step_counter = 0
        
        print(f"\n{'='*60}")
        print(f"🧠 Multi-Step Reasoning Agent")
        print(f"Question: {query}")
        print(f"{'='*60}\n")
        
        # Phase 1: Plan
        print("📋 Phase 1: Planning...")
        plan = await self.plan(query)
        print(f"   Goal: {plan.goal}")
        for i, step in enumerate(plan.steps, 1):
            print(f"   {i}. {step}")
        
        # Phase 2: Execute steps
        print("\n⚡ Phase 2: Executing plan...")
        while plan.current_step < len(plan.steps) and plan.current_step < self.max_steps:
            print(f"\n   Step {plan.current_step + 1}/{len(plan.steps)}: {plan.steps[plan.current_step]}")
            await self.execute_step(plan, plan.current_step, query)
            
            # Reflect after each step
            should_continue = await self.reflect(plan, query)
            if not should_continue:
                print("   🛑 Reflection: Stopping early")
                break
        
        # Phase 3: Synthesize
        print("\n✨ Phase 3: Synthesizing answer...")
        answer = await self.synthesize(query)
        
        print(f"\n{'='*60}")
        print(f"✅ FINAL ANSWER:")
        print(answer)
        print(f"{'='*60}\n")
        
        return {
            "answer": answer,
            "plan": plan,
            "trace": self.reasoning_trace
        }
    
    def print_trace(self):
        """Print the full reasoning trace."""
        print("\n📝 FULL REASONING TRACE:")
        print("-" * 40)
        for step in self.reasoning_trace:
            icon = {
                StepType.PLAN: "📋",
                StepType.THINK: "💭",
                StepType.ACT: "🔧",
                StepType.OBSERVE: "👁️",
                StepType.REFLECT: "🤔",
                StepType.SYNTHESIZE: "✨"
            }.get(step.step_type, "•")
            
            print(f"{icon} Step {step.step_number} [{step.step_type.value}]: {step.content}")
            if step.tool_name:
                print(f"     └─ Tool: {step.tool_name}({step.tool_args})")
            if step.tool_result:
                result_str = json.dumps(step.tool_result)[:150]
                print(f"     └─ Result: {result_str}...")


async def demo():
    """Run demo queries."""
    agent = MultiStepAgent()
    
    test_queries = [
        "How many containers are running and what are their names?",
        "Why did my container 'web-server' crash? Check its logs and status.",
        "Give me a summary of all containers including their resource usage.",
    ]
    
    for query in test_queries:
        result = await agent.run(query)
        agent.print_trace()


async def interactive():
    """Interactive mode."""
    agent = MultiStepAgent()
    
    print("\n" + "="*60)
    print("🤖 Multi-Step Reasoning Agent (Level 5f)")
    print("   Shows explicit reasoning: Plan → Think → Act → Observe → Reflect")
    print("   Type 'exit' to quit, 'trace' to see full reasoning trace")
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
        
        if user_input.lower() == "trace":
            agent.print_trace()
            continue
        
        try:
            await agent.run(user_input)
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