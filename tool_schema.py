
calculate_schema = {
    "type": "function",
    "name": "calculate",
    "description": "Perform basic arithmetic on two numbers.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {
                "type": "number",
                "description": "First number"
            },
            "b": {
                "type": "number",
                "description": "Second number"
            },
            "operation": {
                "type": "string",
                "enum": ["add", "subtract", "multiply", "divide"],
                "description": "Arithmetic operation to perform"
            }
        },
        "required": ["a", "b", "operation"],
        "additionalProperties": False
    },
    "strict": True
}


read_file_schema = {
    "type": "function",
    "name": "read_file",
    "description": "Read a UTF-8 text file from the agent workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file, e.g. report.txt"
            }
        },
        "required": ["path"],
        "additionalProperties": False
    },
    "strict": True
}


write_file_schema = {
    "type": "function",
    "name": "write_file",
    "description": "Write UTF-8 text to a file in the agent workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the output file"
            },
            "content": {
                "type": "string",
                "description": "Text content to write into the file"
            }
        },
        "required": ["path", "content"],
        "additionalProperties": False
    },
    "strict": True
}


search_files_schema = {
    "type": "function",
    "name": "search_files",
    "description": "Search for a keyword in UTF-8 text files in the agent workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in text files"
            }
        },
        "required": ["keyword"],
        "additionalProperties": False
    },
    "strict": True
}


import json

tools = [
    calculate_schema,
    read_file_schema,
    write_file_schema,
    search_files_schema
]

if __name__ == "__main__":
    for tool in tools:
        print(tool["name"])