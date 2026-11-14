
from tool_impl import calculate, read_file, write_file, search_files

tool_handlers = {
    "calculate": calculate,
    "read_file": read_file,
    "write_file": write_file,
    "search_files": search_files
}

required_args = {
    "calculate": {"a", "b", "operation"},
    "read_file": {"path"},
    "write_file": {"path", "content"},
    "search_files": {"keyword"}
}


def dispatch_tool(name: str, args: dict):
    if name not in tool_handlers:
        raise ValueError(f"Unknown tool: {name}")

    if not isinstance(args, dict):
        raise ValueError("Arguments must be a dictionary")

    if set(args) != required_args[name]:
        raise ValueError(f"Invalid arguments for {name}")

    if name == "calculate":
        if type(args["a"]) not in (int, float):
            raise ValueError("a must be a number")

        if type(args["b"]) not in (int, float):
            raise ValueError("b must be a number")

        if not isinstance(args["operation"], str):
            raise ValueError("operation must be a string")

    elif name == "read_file":
        if not isinstance(args["path"], str):
            raise ValueError("path must be a string")

    elif name == "write_file":
        if not isinstance(args["path"], str):
            raise ValueError("path must be a string")

        if not isinstance(args["content"], str):
            raise ValueError("content must be a string")

    elif name == "search_files":
        if not isinstance(args["keyword"], str):
            raise ValueError("keyword must be a string")

    func = tool_handlers[name]
    return func(**args)
