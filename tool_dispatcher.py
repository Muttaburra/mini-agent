
from tool_impl import calculate

tool_handlers = {
    "calculate": calculate
}


def dispatch_tool(name: str, args: dict) -> float:
    if name not in tool_handlers:
        raise ValueError(f"Unknown tool: {name}")

    if set(args) != {"a", "b", "operation"}:
        raise ValueError("Invalid arguments")

    for key in ("a", "b"):
        if type(args[key]) not in (int, float):
            raise ValueError(f"{key} must be a number")

    if not isinstance(args["operation"], str):
        raise ValueError("operation must be a string")

    func = tool_handlers[name]
    return func(**args)
