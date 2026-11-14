
# Mini Agent

A minimal AI Agent Runtime built from scratch in Python.

## Features

- LLM API integration
- Tool Calling with JSON Schema
- Tool Dispatcher
- Multi-step Agent Loop
- Basic argument validation
- Maximum execution steps
- Explicit network timeouts and bounded retries
- Offline API failure and HTTP transport fault-injection tests

## Project Structure

- agent_loop.py: Agent Runtime
- tool_schema.py: Tool definitions
- tool_dispatcher.py: Tool routing and validation
- tool_impl.py: Python tool implementations
- llm_client.py: API error handling, timeouts and retry policy
- tests/: Offline unit and integration tests

## Installation

Create and activate a Python virtual environment.

Install dependencies:

    python -m pip install -r requirements.txt

Configure OPENAI_API_KEY in a local .env file.

## Run

    python agent_loop.py

## Current Limitations

Tools include calculate, read_file, write_file and search_files.
Retry policy currently covers timeouts, connection failures and HTTP 429.
It does not yet handle Retry-After, jitter, quota-specific 429 errors, 5xx retries,
or an overall Agent deadline.

## Offline Tests

No API key or real network request is needed:

    python -m unittest discover -s tests -v

Tests replace SDK or HTTP transport boundaries and isolate tool execution from
workspace data. See [Day 5 acceptance notes](docs/week1_day5_acceptance.md).
