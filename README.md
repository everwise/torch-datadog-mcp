# DataDog MCP Server

A [FastMCP](https://github.com/jlowin/fastmcp) server providing DataDog log search and monitoring capabilities through the Model Context Protocol (MCP).

## Features

- **Service-Aware Log Search**: Search DataDog logs with service-specific filtering for enhanced targeting
- **Tasmania Space Filtering**: Filter tasmania service logs by space ID, user, or tenant
- **Meeting-Specific Debugging**: Find all logs related to specific meetings (7-day default)
- **User Activity Tracking**: Search user-related logs and activities across services
- **Webhook Event Analysis**: Find integration webhook events for Zoom and Whereby
- **Error Detection**: Search for recent errors across services with intelligent filtering
- **APM Trace Correlation**: Find all logs for specific traces
- **STDIO Transport**: Self-contained server for local MCP usage
- **Environment-Based Configuration**: Secure API key management

## Response Size Safeguards

The MCP server includes comprehensive safeguards to prevent overwhelming LLM contexts with massive log responses:

### Automatic Protections
- **Response Size Limit**: Responses are capped at 500KB total
- **Per-Log Limits**: Individual log entries are limited to 10KB
- **Payload Filtering**: Large request/response data is automatically truncated with summaries
- **Query Validation**: Warns about overly broad searches before execution

### Size Management Features
- **Smart Truncation**: Large fields show truncated content with original size information
- **Early Termination**: Processing stops when size limits are reached
- **Clear Messaging**: Responses indicate when truncation occurs and why

### Response Indicators
```json
{
  "logs": [...],
  "response_size_bytes": 45120,
  "truncated": true,
  "truncation_reason": "Response size limit exceeded",
  "skipped_logs": 15,
  "recommendation": "Use more specific filters or pagination to reduce response size",
  "query_warnings": {
    "risk_level": "high",
    "warnings": ["Literal string search without specific field filters"],
    "recommendations": ["Add specific field filters like service:meeting"]
  }
}
```

## Preview-Then-Execute Workflow (RECOMMENDED)

For large or uncertain queries, use the two-step preview workflow to avoid overwhelming responses:

### Step 1: Preview the Query
```bash
# Preview potentially large queries first using structured filters
preview = preview_search(service="meeting", user_id=214413, hours=24, limit=100)
```

**Preview Response:**
```json
{
  "estimated_count": 150,
  "estimated_size_mb": 0.3,
  "sample_logs": [...],  // 3 sample entries for structure
  "cache_id": "abc123-def456-...",
  "expires_in_seconds": 30,
  "execution_recommendation": "OK",
  "query_warnings": {
    "risk_level": "low",
    "warnings": [],
    "recommendations": ["Query looks well-targeted with service and user filters"]
  }
}
```

### Step 2: Execute or Refine
```bash
# If preview looks reasonable, execute with cache_id
if preview["execution_recommendation"] == "OK":
    results = search_logs(cache_id=preview["cache_id"])
else:
    # Refine with more specific structured filters
    refined_results = search_logs(
        service="meeting",
        meeting_id=136666,
        status="ERROR",
        hours=6
    )
```

## Best Practices

### ✅ Recommended Query Patterns
```bash
# BEST: Use structured filters with specific service
search_logs(service="meeting", meeting_id=136666, status="ERROR", hours=2)

# User-specific filtering across services
search_logs(service="tasmania", user_id=214413, hours=6)

# Space-specific filtering (Tasmania coaching spaces)
search_logs(service="tasmania", space_id=168565, hours=12)

# Actor email filtering (finds user activity across log formats)
search_logs(service="meeting", actor_email="user@example.com", hours=24)

# PREVIEW FIRST: For potentially large result sets
preview = preview_search(service="meeting", user_id=214413, hours=24)
if preview["execution_recommendation"] == "OK":
    results = search_logs(cache_id=preview["cache_id"])
```

### ❌ Avoid These Patterns (Will Trigger Warnings)
```bash
# WRONG: Raw DataDog query strings (defeats smart filtering)
search_logs(query='env:prod "meeting_id:136666"', hours=24)

# TOO BROAD: No service or specific filters
search_logs(query="env:prod", hours=12)

# HIGH VOLUME: Long time range without targeted filters
search_logs(hours=48, limit=200)
```

## Service-Specific Filtering

The DataDog MCP server automatically adapts filtering based on the service being queried. Each service has its own set of available filters:

### Supported Services

| Service | Available Filters | Description |
|---------|------------------|-------------|
| `tasmania` | `user_id`, `tenant_id`, `space_id` | Coaching platform logs with space-based filtering |
| `meeting` | `user_id`, `tenant_id`, `meeting_id`, `path_id` | Meeting service logs |
| `assessment` | `user_id`, `tenant_id`, `assessment_id` | Assessment service logs |
| `integration` | `user_id`, `tenant_id`, `meeting_id`, `provider` | Integration service logs |

### Filter Examples

```bash
# Tasmania space-specific filtering (maps to path filtering)
search_logs(service="tasmania", space_id=168565, user_id=214413)

# Meeting service error tracking
search_logs(service="meeting", meeting_id=136666, status="ERROR")

# Actor email filtering (finds user activity across different log formats)
search_logs(service="meeting", actor_email="user@example.com", hours=24)

# Integration provider filtering
search_logs(service="integration", provider="zoom", meeting_id=136666)
```

## Installation

### Requirements

- Python 3.11+
- DataDog API key and Application key
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

#### Option 1: Install as Global CLI Tool (Recommended)

1. **Install as a global CLI tool using uv**:
   ```bash
   uv tool install git+https://github.com/everwise/torch-datadog-mcp.git
   ```

   Or using pipx:
   ```bash
   pipx install git+https://github.com/everwise/torch-datadog-mcp.git
   ```

   Or add to project dependencies:
   ```bash
   uv add git+https://github.com/everwise/torch-datadog-mcp.git
   ```

2. **Set environment variables**:
   ```bash
   export DD_API_KEY=your_api_key_here
   export DD_APP_KEY=your_app_key_here
   export DD_SITE=datadoghq.com  # Optional, default shown
   ```

#### Option 2: Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/everwise/torch-datadog-mcp.git
   cd torch-datadog-mcp
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
   # Create .env file with your DataDog credentials
   touch .env
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
# If installed from GitHub
datadog-mcp

# For local development with uv
uv run --project /path/to/torch-datadog-mcp datadog-mcp

# Alternative local development commands
uv run python -m datadog_mcp.server
python src/datadog_mcp/server.py
```

The server runs in STDIO mode by default, making it suitable for MCP clients.

### Available Tools

The server provides 8 focused tools for DataDog log analysis:

#### Core Search Tools
- **`preview_search`**: Preview query size and count before execution (30s cache)
- **`search_logs`**: Enhanced main search with service-aware filtering and size safeguards
- **`get_trace_logs`**: Get all logs for a specific APM trace ID

#### Business Analysis Tools
- **`search_business_events`**: Find business events across services
- **`trace_request_flow`**: Track requests across multiple services using correlation IDs

#### Utility Tools
- **`test_connection`**: Test DataDog API connectivity
- **`get_server_info`**: Get server configuration information
- **`debug_configuration`**: Get detailed debugging information

#### Service-Specific Structured Filters
Use these structured filters with the `search_logs` tool (automatically maps to correct DataDog fields):

**Tasmania Service:**
- `user_id` → Maps to current user context fields
- `tenant_id` → Maps to current tenant context
- `space_id` → Maps to space path filtering (`/api/v1/spaces/{id}*`)
- `actor_email` → Maps to statement actor email fields

**Meeting Service:**
- `meeting_id` → Maps to meeting ID field
- `user_id` → Maps to user ID field
- `tenant_id` → Maps to tenant ID field
- `path_id` → Maps to notifiable ID (learning paths)
- `actor_email` → Maps to events actor email

**Assessment Service:**
- `assessment_id` → Maps to assessment ID field
- `user_id`, `tenant_id` → Standard user/tenant filtering

**Integration Service:**
- `provider` → Filter by integration provider (zoom, whereby)
- `meeting_id` → Maps to meeting ID field
- `user_id`, `tenant_id` → Standard user/tenant filtering

## Claude Desktop Integration

Add this configuration to your Claude Desktop config file:

### macOS
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

#### For Global Tool Installation (Recommended)
```json
{
  "mcpServers": {
    "datadog": {
      "command": "datadog-mcp",
      "env": {
        "DD_API_KEY": "your_api_key_here",
        "DD_APP_KEY": "your_app_key_here",
        "DD_SITE": "datadoghq.com"
      }
    }
  }
}
```

#### For Local Development Setup
```json
{
  "mcpServers": {
    "datadog": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/torch-datadog-mcp", "datadog-mcp"],
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

### Alternative: Using Environment Variables
If you set environment variables globally, you can omit the `env` section:

```json
{
  "mcpServers": {
    "datadog": {
      "command": "datadog-mcp"
    }
  }
}
```

## Example Usage Patterns

### Debug Meeting Issues
```python
# Find all logs for a specific meeting
search_logs(service="meeting", meeting_id=136666, hours=24)

# Focus on errors for that meeting
search_logs(service="meeting", meeting_id=136666, status="ERROR", hours=168)
```

### Find Integration Events
```python
# Zoom integration events for a meeting
search_logs(service="integration", provider="zoom", meeting_id=136667)

# All integration activity for a user
search_logs(service="integration", user_id=214413, hours=48)
```

### Monitor Service Health
```python
# Recent errors in meeting service
search_logs(service="meeting", status="ERROR", hours=2)

# Tasmania space-specific errors
search_logs(service="tasmania", space_id=168565, status="ERROR", hours=6)
```

### User Activity Tracking
```python
# All activity for a user in Tasmania
search_logs(service="tasmania", actor_email="user@example.com", hours=24)

# User's meeting activity
search_logs(service="meeting", user_id=214413, hours=12)
```

### APM Trace Investigation
```python
# Find all logs for a trace (works across services)
get_trace_logs(trace_id="1234567890abcdef", hours=1)

# Track a request across services
trace_request_flow(request_id="req_abc123", hours=2)
```

## Query Architecture

The server uses **structured filters** that automatically map to the correct DataDog fields:

### Structured Filter Benefits
- **Smart Field Mapping**: `user_id=214413` maps to the right field(s) per service
- **OR Conditions**: Automatically searches multiple possible field locations
- **Health Check Exclusion**: Removes noise from health check endpoints
- **Service-Aware**: Each service has optimized field mappings

### Common Structured Patterns
```python
# Service + specific entity
search_logs(service="meeting", meeting_id=136666)

# User activity across services
search_logs(service="tasmania", user_id=214413)

# Status filtering with context
search_logs(service="meeting", meeting_id=136666, status="ERROR")

# Actor-based filtering (email)
search_logs(service="meeting", actor_email="user@example.com")
```

## Default Time Ranges

- General log search: 24 hours
- Trace logs: 1 hour
- Business events: 24 hours
- Request flow tracing: 1 hour

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
│       └── filter_config.py # Service-specific filter configuration
├── pyproject.toml           # Project configuration
├── .env                     # Environment variables (create this)
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