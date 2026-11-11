
import json
from dotenv import load_dotenv
from openai import OpenAI
from tool_schema import calculate_schema
from tool_dispatcher import dispatch_tool

load_dotenv()
client = OpenAI()

response = client.responses.create(
    model="gpt-6-luna",
    input=(
    "请严格按顺序使用 calculate 工具完成两个步骤："
    "第一步计算 35 × 18；"
    "收到第一步的工具执行结果后，"
    "第二步再使用 calculate 工具将该结果加上 120。"
    "不要跳过任何一次工具调用，最后告诉我计算结果。"),
    tools=[calculate_schema],
    tool_choice="required",
    parallel_tool_calls=False
)

max_steps = 5
step = 0

while step < max_steps:
    step += 1

    print(f"Round {step}")

    if response.status != "completed":
        print("Model response incomplete:", response.status)
        break

    tool_calls = [
        item for item in response.output
        if item.type == "function_call"
    ]

    if not tool_calls:
        print("Final answer:", response.output_text)
        break

    tool_outputs = []

    for item in tool_calls:
        try:
            args = json.loads(item.arguments)
            result = dispatch_tool(item.name, args)
            output = str(result)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            output = f"Tool error: {e}"

        print("Tool:", item.name)
        print("Result:", output)

        tool_outputs.append({
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": output
        })

    
    response = client.responses.create(
        model="gpt-6-luna",
        previous_response_id=response.id,
        input=tool_outputs,
        tools=[calculate_schema],
        tool_choice="auto",
        parallel_tool_calls=False
    )

