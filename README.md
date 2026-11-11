
# Mini Agent

A minimal AI Agent Runtime built from scratch in Python.

## Features

- LLM API integration
- Tool Calling with JSON Schema
- Tool Dispatcher
- Multi-step Agent Loop
- Basic argument validation
- Maximum execution steps

## Project Structure

- agent_loop.py: Agent Runtime
- tool_schema.py: Tool definitions
- tool_dispatcher.py: Tool routing and validation
- tool_impl.py: Python tool implementations

## Installation

Create and activate a Python virtual environment.

Install dependencies:

    python -m pip install -r requirements.txt

Configure OPENAI_API_KEY in a local .env file.

## Run

    python agent_loop.py

## Current Limitations

Only the calculate tool is implemented.
File operations and production error handling are planned.
