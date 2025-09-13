# DataDog MCP Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that provides DataDog log search and monitoring capabilities through the Model Context Protocol (MCP).

## Features

- **Comprehensive Log Search**: Search DataDog logs using flexible queries
- **Meeting-Specific Debugging**: Find all logs related to specific meetings (7-day default)
- **User Activity Tracking**: Search user-related logs and activities
- **Webhook Event Analysis**: Find integration webhook events for Zoom and Whereby
- **Error Detection**: Search for recent errors across services
- **APM Trace Correlation**: Find all logs for specific traces
- **STDIO Transport**: Self-contained server for local MCP usage
- **Environment-Based Configuration**: Secure API key management

## Installation

### Requirements

- Python 3.11+
- DataDog API key and Application key
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

1. **Clone or create the project**:
   ```bash
   cd ~/dev/torch-datadog-mcp
   ```

2. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your DataDog credentials
   ```

4. **Set your DataDog API keys** in `.env`:
   ```bash
   DD_API_KEY=your_api_key_here
   DD_APP_KEY=your_app_key_here
   DD_SITE=datadoghq.com  # Optional, default shown
   ```

### Getting DataDog API Keys

1. Go to [DataDog Organization Settings > API Keys](https://app.datadoghq.com/organization-settings/api-keys)
2. Create or copy your **API Key**
3. Go to [Application Keys](https://app.datadoghq.com/organization-settings/application-keys)
4. Create or copy your **Application Key**

## Usage

### Running the Server

```bash
# Using uv
uv run python -m datadog_mcp.server

# Using the installed script
datadog-mcp

# Or directly
python src/datadog_mcp/server.py
```

The server runs in STDIO mode by default, making it suitable for MCP clients.

### Available Tools

#### `search_logs`
Search DataDog logs with custom queries.
```json
{
  "query": "env:prod service:meeting status:ERROR",
  "hours": 2,
  "limit": 50
}
```

#### `search_meeting_logs`
Find all logs related to a specific meeting (7-day default lookback).
```json
{
  "meeting_id": 136666,
  "hours": 168
}
```

#### `search_user_logs`
Find all logs related to a specific user.
```json
{
  "user_id": 12345,
  "hours": 24
}
```

#### `search_webhook_events`
Find webhook events for meeting integrations.
```json
{
  "meeting_id": 136666,
  "provider": "zoom",
  "hours": 168
}
```

#### `search_errors`
Find recent errors across services.
```json
{
  "service": "meeting",
  "hours": 2
}
```

#### `search_trace`
Find all logs for a specific APM trace.
```json
{
  "trace_id": "1234567890abcdef",
  "hours": 1
}
```

#### `test_connection`
Test DataDog API connectivity.
```json
{}
```

#### `get_server_info`
Get server configuration information.
```json
{}
```

## Claude Desktop Integration

Add this configuration to your Claude Desktop config file:

### macOS
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "datadog": {
      "command": "uv",
      "args": ["run", "python", "-m", "datadog_mcp.server"],
      "cwd": "/path/to/torch-datadog-mcp",
      "env": {
        "DD_API_KEY": "your_api_key_here",
        "DD_APP_KEY": "your_app_key_here",
        "DD_SITE": "datadoghq.com"
      }
    }
  }
}
```

### Windows
Edit `%APPDATA%\\Claude\\claude_desktop_config.json` with similar configuration.

### Alternative: Environment File
If you prefer to use the `.env` file:

```json
{
  "mcpServers": {
    "datadog": {
      "command": "uv",
      "args": ["run", "python", "-m", "datadog_mcp.server"],
      "cwd": "/path/to/torch-datadog-mcp"
    }
  }
}
```

## Example Queries

### Debug Meeting Issues
```
Search for logs related to meeting 136666 over the past 7 days
```

### Find Integration Errors
```
Search for Zoom webhook events for meeting 136667
```

### Monitor Service Health
```
Search for errors in the meeting service over the past 2 hours
```

### Trace Investigation
```
Search for all logs in trace 1234567890abcdef
```

## Query Patterns

The server uses DataDog's log search syntax. Common patterns:

- **Service filtering**: `service:meeting`, `service:integration`
- **Environment filtering**: `env:prod`, `env:staging`
- **Status filtering**: `status:ERROR`, `status:WARNING`
- **Custom attributes**: `@meeting_id:123`, `@user_id:456`
- **Zoom webhooks**: `@payload.payload.object.id:meeting_id`
- **Whereby webhooks**: `@request_identifiers.resource_id:meeting_id`

## Default Time Ranges

- General log search: 1 hour
- Meeting logs: 168 hours (7 days)
- User logs: 24 hours
- Webhook events: 168 hours (7 days)
- Error search: 2 hours
- Trace search: 1 hour

## Development

### Running Tests
```bash
uv run pytest
```

### Code Formatting
```bash
uv run ruff format
uv run ruff check
```

### Project Structure
```
torch-datadog-mcp/
├── src/
│   └── datadog_mcp/
│       ├── __init__.py
│       ├── server.py        # FastMCP server with tools
│       ├── client.py        # DataDog API client
│       └── settings.py      # Environment configuration
├── pyproject.toml           # Project configuration
├── .env.example             # Example environment variables
├── README.md                # This file
└── datadog-mcp.fastmcp.json # FastMCP configuration
```

## Troubleshooting

### Authentication Issues
- Verify `DD_API_KEY` and `DD_APP_KEY` are set correctly
- Check your DataDog site setting (`DD_SITE`)
- Ensure keys have appropriate permissions for log search

### Connection Problems
- Use the `test_connection` tool to verify API connectivity
- Check network connectivity to DataDog endpoints
- Verify your DataDog organization has log access enabled

### No Results Found
- Check time ranges (use longer periods for older data)
- Verify query syntax matches DataDog's log search format
- Ensure the environment/service filters match your data

## License

MIT License - see LICENSE file for details.