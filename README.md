# MCP Calculator Server

A simple and efficient MCP (Model Context Protocol) server that provides mathematical calculation capabilities through Python expressions.

## Features

- ✨ **Mathematical Calculations**: Evaluate Python expressions with full math module support
- 🎲 **Random Number Generation**: Access to Python's random module
- 🔒 **Safe Evaluation**: Sandboxed execution environment
- 📡 **STDIO Transport**: Easy integration with MCP clients

## Installation

### Using uvx (Recommended)

```bash
uvx mcp-calculator
```

### Using pip

```bash
pip install mcp-calculator
```

### From Source

```bash
git clone https://github.com/quyen-nguyen-270898/mcp-calculator.git
cd mcp-calculator
pip install -e .
```

## Usage

### Running the Server

```bash
python calculator.py
```

Or if installed:

```bash
mcp-calculator
```

### Available Tools

#### calculator

Evaluates Python mathematical expressions with support for:
- Basic arithmetic: `+`, `-`, `*`, `/`, `**`, `%`
- Math module functions: `math.sqrt()`, `math.sin()`, `math.cos()`, etc.
- Random module: `random.random()`, `random.randint()`, etc.

**Input Schema:**
```json
{
  "python_expression": "string (required) - A valid Python expression to evaluate"
}
```

**Examples:**
- `2 + 2`
- `math.sqrt(16)`
- `math.pi * 2`
- `random.randint(1, 100)`
- `(5 + 3) * 2 - 4`

### Integration with MCP Clients

#### Claude Desktop Configuration

Add to your Claude Desktop config file:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "calculator": {
      "command": "uvx",
      "args": ["mcp-calculator"]
    }
  }
}
```

Or using Python directly:

```json
{
  "mcpServers": {
    "calculator": {
      "command": "python",
      "args": ["path/to/calculator.py"]
    }
  }
}
```

#### Using with imcp.pro

This MCP server can be easily added to imcp.pro:

1. **From GitHub**: Simply paste the repository URL in imcp.pro
2. **Manual Addition**:
   - **Mode**: STDIO
   - **Command**: `uvx`
   - **Parameters**: `mcp-calculator`
   - No environment variables required

## Development

### Requirements

- Python 3.10 or higher
- No external dependencies

### Testing

Run the server and send JSON-RPC messages via stdin:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python calculator.py
```

## Protocol Details

This server implements the Model Context Protocol (MCP) specification:
- Protocol Version: 2024-11-05
- Transport: STDIO
- Supported Methods:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `ping`

## Security Notes

⚠️ The calculator uses Python's `eval()` with a restricted environment:
- No access to `__builtins__`
- Only `math` and `random` modules are available
- No file system or network access

While this provides basic sandboxing, use caution with untrusted input.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Check existing issues for solutions

## Changelog

### v1.0.0 (2026-01-30)
- Initial release
- Basic calculator functionality
- Math and random module support
- STDIO transport implementation
