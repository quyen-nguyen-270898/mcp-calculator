#!/usr/bin/env node
import { spawn } from 'child_process';

// Check if uvx is available
const uvx = spawn('uvx', ['--version'], { stdio: 'pipe' });

uvx.on('error', () => {
  console.error('Error: uvx not found. Please install uv first:');
  console.error('curl -LsSf https://astral.sh/uv/install.sh | sh');
  process.exit(1);
});

uvx.on('exit', (code) => {
  if (code === 0) {
    // uvx is available, run the Python MCP server
    const server = spawn('uvx', [
      '--from',
      'git+https://github.com/quyen-nguyen-270898/mcp-calculator.git',
      'mcp-calculator'
    ], {
      stdio: 'inherit'
    });

    server.on('exit', (code) => {
      process.exit(code || 0);
    });
  } else {
    console.error('Error: uvx command failed');
    process.exit(1);
  }
});
