# mcp-calculator
MCP server to calculate

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variable:
```bash
export MCP_ENDPOINT='wss://your-endpoint-url'
```

3. Run locally:
```bash
python3 mcp_pipe.py
```

## Deploy to Render

1. Push code to GitHub

2. Create new Web Service on Render:
   - Connect your GitHub repository
   - Select branch: `main`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python server.py`

3. Add Environment Variable:
   - Key: `MCP_ENDPOINT`
   - Value: Your WebSocket endpoint URL

4. Deploy!

The service will:
- Start an HTTP server on port 10000 for Render health checks
- Run MCP pipe in background to connect calculator to your endpoint
- Auto-restart if MCP connection fails

Health check endpoint: `https://your-app.onrender.com/health`
