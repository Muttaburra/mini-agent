from pathlib import Path


def calculate(a: float, b: float, operation: str) -> float:
    # Annotations do not validate runtime inputs; bool is an int subclass.
    if type(a) not in (int, float) or type(b) not in (int, float):
        raise ValueError("a and b must be numbers")
    if not isinstance(operation, str):
        raise ValueError("operation must be a string")

    if operation == "add":
        return a + b

    if operation == "subtract":
        return a - b

    if operation == "multiply":
        return a * b

    if operation == "divide":
        if b == 0:
            raise ValueError("Division by zero is not allowed")
        return a / b

    raise ValueError(f"Unsupported operation: {operation}")


WORKSPACE = (
    Path(__file__).resolve().parent / "workspace"
).resolve()


def read_file(path: str) -> str:
    requested = Path(path)

    if requested.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    target = (WORKSPACE / requested).resolve()

    if not target.is_relative_to(WORKSPACE):
        raise ValueError("Path outside workspace")

    if target.suffix.lower() != ".txt":
        raise ValueError("Only .txt files are allowed")

    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    return target.read_text(encoding="utf-8")



MAX_WRITE_BYTES = 16 * 1024


def write_file(path: str, content: str) -> str:
    if not isinstance(path, str) or not isinstance(content, str):
        raise ValueError("path and content must be strings")

    requested = Path(path)

    if requested.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    target = (WORKSPACE / requested).resolve()

    if not target.is_relative_to(WORKSPACE):
        raise ValueError("Path outside workspace")

    if target.suffix.lower() != ".txt":
        raise ValueError("Only .txt files are allowed")

    if not target.parent.is_dir():
        raise FileNotFoundError("Parent directory does not exist")

    if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
        raise ValueError("File content is too large")

    with target.open("x", encoding="utf-8") as f:
        f.write(content)

    return f"Created file: {target.relative_to(WORKSPACE)}"



def search_files(keyword: str) -> list[dict]:
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("Keyword must be a non-empty string")

    results = []

    for path in WORKSPACE.rglob("*.txt"):
        target = path.resolve()

        if not target.is_relative_to(WORKSPACE):
            continue

        if not target.is_file():
            continue

        if target.stat().st_size > 16 * 1024:
            continue

        relative_path = target.relative_to(WORKSPACE).as_posix()
        content = read_file(relative_path)

        for line_num, line in enumerate(content.splitlines(), start=1):
            if keyword.casefold() in line.casefold():
                results.append({
                    "file": relative_path,
                    "line": line_num,
                    "text": line[:200]
                })

                if len(results) >= 20:
                    return results

    return results
