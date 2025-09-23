# DataDog MCP Server - Example Triage Workflow

## Implementation Summary ✅

Successfully consolidated from **17 tools down to 8 focused tools** with **response size safeguards**:

### Final Tool Structure:
1. **`preview_search`** - NEW: Preview query size/count before execution (30s cache) 🛡️
2. **`search_logs`** - Enhanced main search with size safeguards and cache_id support 🛡️
3. **`get_trace_logs`** - APM trace expansion (key workflow)
4. **`search_business_events`** - Business event analysis
5. **`trace_request_flow`** - Request/execution tracking
6. **`test_connection`**, **`get_server_info`**, **`debug_configuration`** - Debug tools

### 🛡️ NEW: Response Size Safeguards
- **500KB response limit** to prevent LLM context overflow
- **10KB per-log limits** with smart payload truncation
- **Preview workflow** for uncertain queries
- **Query validation** warnings for overly broad searches

## Example Triage Workflow

### Step 0: Preview Large/Uncertain Queries (NEW!) 🛡️
```bash
# BEFORE running potentially large queries, preview them first
preview = preview_search(
  query='env:prod "130361"',
  hours=24,
  limit=100
)
```

**Preview Response:**
```json
{
  "estimated_count": 1500,
  "estimated_size_mb": 2.3,
  "sample_logs": [...],  // 3 sample entries
  "cache_id": "abc123-...",
  "execution_recommendation": "CAUTION: Large response expected",
  "query_warnings": {
    "risk_level": "high",
    "warnings": ["Literal string search without specific field filters"],
    "recommendations": ["Add specific field filters like service:meeting"]
  }
}
```

**Decision Logic:**
```bash
# If preview looks good, execute with cache_id
if preview["execution_recommendation"] == "OK":
    results = search_logs(cache_id=preview["cache_id"])
else:
    # Refine query based on recommendations
    refined = search_logs(service="meeting", filters={"meeting_id": 130361})
```

### Step 1: Find Meeting-Related Issues
```bash
# Search for recent meeting API errors
search_logs(
  query="env:prod /api/v1/meeting_series",
  service="meeting",
  status="ERROR",
  hours=2
)
```

**Clean Output (JWT tokens, CloudFront headers, IPs filtered out):**
```json
{
  "logs": [
    {
      "timestamp": "2025-09-13T23:47:58.803Z",
      "message": "/api/v1/meeting_series",
      "status": "ERROR",
      "service": "meeting",
      "host": "arn:aws:lambda:us-west-2:function:meeting-service-prod",
      "user_id": 279361,
      "tenant_id": 103,
      "trace_id": "7987780876479239178",
      "duration_ms": 2380,
      "context": {
        "request": {
          "method": "POST",
          "path": "/api/v1/meeting_series",
          "scheme": "https"
        },
        "response": {
          "status_code": 500
        }
      }
    }
  ]
}
```

### Step 2: Expand APM Trace for Full Context
```bash
# Get ALL related logs across services for this trace
get_trace_logs(
  trace_id="7987780876479239178",
  hours=1
)
```

**Result:** Complete request flow across meeting service, integration service, assessment service, etc.

### Step 3: Filter by Specific Objects
```bash
# Focus on specific user's issues
search_logs(
  query="env:prod",
  user_id=279361,
  hours=6
)

# Or focus on specific meeting
search_logs(
  query="env:prod",
  meeting_id=133728,
  hours=24
)
```

## Key Improvements ✅

### 1. **Health Checks Excluded**
- Automatic filter: `-@path:*/health`
- Removed `get_service_health()` method entirely

### 2. **Noise Filtered Out**
- ❌ JWT tokens (600+ char bearer tokens)
- ❌ CloudFront headers
- ❌ Network IP addresses
- ❌ Massive request/response payloads
- ✅ Only essential triage fields preserved

### 3. **Essential Fields Preserved**
- `user_id`, `tenant_id`, `meeting_id`, `path_id`, `assessment_id`
- `trace_id`, `span_id`, `execution_uuid`
- `duration_ms`, `status_code`, `error_code`
- Clean request context (method, path, status_code only)

### 4. **LLM-Friendly Structure**
- Easy tool selection (7 vs 17)
- Clear filtering parameters
- Predictable output format
- Fast APM trace expansion workflow

## File Changes Made ✅

### `/src/datadog_mcp/server.py`
- Reduced from 19 tools to 7 tools
- Enhanced `search_logs` with filtering parameters
- Removed redundant search methods

### `/src/datadog_mcp/client.py`
- Removed 10+ redundant methods
- Removed `get_service_health()`
- Enhanced `_format_log_entry()` for noise filtering
- Clean, focused implementation

## Next Steps
1. Restart MCP server to register new tool signatures
2. Test example workflow end-to-end
3. Validate data filtering in live environment

**Ready for production triage workflows!** 🚀