# Langchain
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import create_agent

# System package
import subprocess   #Package that can run cmmand in your terminal


SYSTEM_PROMPT = """
You are a Docker expert. you can explain things in 1-2 lines max.
You dont overthink, hallunicate or keep reasoning in loop.
You reason and act according to user prompt.

these are the things you do:
1/ You tell bout errors (what went wrong, etc)
2/ You tell about root cause (What was the cause likely)
3/ You tell about the fix or solution short
"""

@tool
def running_containers():
    """Tool:1 Show running Containers"""
    result = subprocess.run(
        ["docker", "ps", "-q"],
        capture_output=True,
        text=True
    )
    return result.stdout

@tool
def container_logs_by_name(container_name):
    # run docker logs command
    """Tool:2 Show Logs of Containers"""
    result = subprocess.run(
        ["docker", "logs", "--tail", "10", container_name],
        capture_output=True,
        text=True
    )
    return result.stdout

llm = ChatOllama(     #LLM 
    model="gemma4:e4b",
    temperature="0.8",
    system=SYSTEM_PROMPT
    )

tools = [running_containers, container_logs_by_name]    #Tools

#   LLM + Tools = Agent

agent = create_agent(llm,tools)

while True:
    user_input = input("Enter your message:\n")
    if user_input == "exit":
        break
    response = agent.invoke ({"messages" : 
                [
                        {'role': 'user','content': user_input,}
                    ]
                    })

    print(response['messages'][-1].content)