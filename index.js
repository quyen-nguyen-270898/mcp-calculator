#!/usr/bin/env node
import { spawn } from 'child_process';

// Directly run the Python MCP server via uvx
const server = spawn('uvx', [
  '--from',
  'git+https://github.com/quyen-nguyen-270898/mcp-calculator.git',
  'mcp-calculator'
], {
  stdio: 'inherit',
  env: process.env
});

server.on('error', (err) => {
  console.error('Failed to start server:', err.message);
  console.error('Make sure uvx is installed: curl -LsSf https://astral.sh/uv/install.sh | sh');
  process.exit(1);
});

server.on('exit', (code) => {
  process.exit(code || 0);
});
