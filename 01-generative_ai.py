import ollama

SYSTEM_PROMPT = """
You are a Docker expert. you can explain things in 1-2 lines max.
You dont overthink, hallunicate or keep reasoning in loop.
You reason and act according to user prompt.

these are the things you do:
1/ You tell bout errors (what went wrong, etc)
2/ You tell about root cause (What was the cause likely)
3/ You tell about the fix or solution short
"""

while True:
    user_input = input("Enter your message:\n")
    if user_input == "exit":
        break
    # Request
    response = ollama.chat(
        model="gemma4:e4b",
        messages=  [{ 'role': 'system', 'content' : SYSTEM_PROMPT}, {
        'role': 'user',
        'content': user_input,
    }]
    )
    print(response['message']['content'])