
def calculate(a: float, b: float, operation: str) -> float:
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


if __name__ == "__main__":
    print(calculate(10, 20, "add"))
    print(calculate(10, 20, "subtract"))
    print(calculate(10, 20, "multiply"))
    print(calculate(10, 4, "divide"))

    try:
        print(calculate(10, 0, "divide"))
    except ValueError as e:
        print("Error:", e)

    try:
        print(calculate(10, 20, "power"))
    except ValueError as e:
        print("Error:", e)

    print("Program finished")
