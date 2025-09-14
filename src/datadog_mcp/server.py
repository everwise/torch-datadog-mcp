from typing import Dict, Any

from fastmcp import FastMCP
from .client import DataDogLogsClient

# Create the MCP server instance
mcp = FastMCP()

_client = None

def get_client():
    global _client
    if _client is None:
        try:
            _client = DataDogLogsClient()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DataDog client: {e}")
    return _client


@mcp.tool
async def search_logs(
    query: str = "env:prod",
    hours: int = 1,
    limit: int = 50,
    cursor: str = None,
    user_id: int = None,
    meeting_id: int = None,
    path_id: int = None,
    assessment_id: int = None,
    tenant_id: int = None,
    service: str = None,
    status: str = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Search DataDog logs with filtering options for triage.

    Args:
        query: Base DataDog search query (default: 'env:prod')
        hours: How many hours back to search (default: 1)
        limit: Maximum number of logs to return (default: 50)
        cursor: Pagination cursor for retrieving subsequent pages (optional)
        user_id: Filter by specific user ID
        meeting_id: Filter by specific meeting ID
        path_id: Filter by specific path ID
        assessment_id: Filter by specific assessment ID
        tenant_id: Filter by specific tenant ID
        service: Filter by service (meeting, assessment, integration, etc.)
        status: Filter by log status (ERROR, WARN, INFO)
        verbose: If True, return all log fields except explicitly blacklisted ones

    Returns:
        Dict containing filtered logs and search metadata
    """
    client = get_client()
    time_from = f"now-{hours}h"

    # Build enhanced query with filters, exclude health checks
    filters = ["-@path:*/health"]  # Exclude health check endpoints
    if user_id:
        filters.append(f"@user_id:{user_id}")
    if meeting_id:
        filters.append(f"@meeting_id:{meeting_id}")
    if path_id:
        filters.append(f"@path_id:{path_id}")
    if assessment_id:
        filters.append(f"@assessment_id:{assessment_id}")
    if tenant_id:
        filters.append(f"@tenant_id:{tenant_id}")
    if service:
        filters.append(f"service:{service}")
    if status:
        filters.append(f"status:{status}")

    enhanced_query = query
    if filters:
        enhanced_query += " " + " ".join(filters)

    try:
        result = await client.search_logs(
            query=enhanced_query,
            time_from=time_from,
            limit=limit,
            cursor=cursor,
            verbose=verbose
        )
        return result
    except Exception as e:
        return {
            'error': str(e),
            'query': enhanced_query,
            'hours': hours
        }


@mcp.tool
async def get_trace_logs(
    trace_id: str,
    hours: int = 1,
    cursor: str = None
) -> Dict[str, Any]:
    """
    Get all logs across ALL services for a given APM trace ID with pagination support.

    Args:
        trace_id: The APM trace ID to search for
        hours: How many hours back to search (default: 1)
        cursor: Pagination cursor for retrieving subsequent pages (optional)

    Returns:
        Dict containing all logs for the trace with pagination info
    """
    client = get_client()

    try:
        result = await client.get_trace_logs(trace_id, hours, cursor)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'trace_id': trace_id,
            'hours': hours
        }


@mcp.tool
async def search_business_events(
    event_type: str,
    service: str = None,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Search for business events across services.

    Args:
        event_type: Type of business event (e.g., 'meeting.started', 'meeting.ended')
        service: Optional service filter (e.g., 'meeting', 'integration')
        hours: How many hours back to search (default: 24)

    Returns:
        Dict containing business event logs
    """
    client = get_client()

    try:
        result = await client.search_business_events(event_type, service, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'event_type': event_type,
            'service': service,
            'hours': hours
        }


@mcp.tool
async def trace_request_flow(
    request_id: str,
    hours: int = 1
) -> Dict[str, Any]:
    """
    Track a request across multiple services using request_id or correlation IDs.

    Args:
        request_id: The request ID or correlation ID to track
        hours: How many hours back to search (default: 1)

    Returns:
        Dict containing request flow logs across all services
    """
    client = get_client()

    try:
        result = await client.trace_request_flow(request_id, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'request_id': request_id,
            'hours': hours
        }


@mcp.tool
async def test_connection() -> Dict[str, Any]:
    """
    Test the DataDog API connection and configuration.

    Returns:
        Dict containing connection status and test results
    """
    client = get_client()
    return await client.test_connection()


@mcp.tool
async def get_server_info() -> Dict[str, Any]:
    """
    Get information about the DataDog MCP server configuration.

    Returns:
        Dict containing server information and configuration
    """
    return {
        'server_name': 'torch-datadog-mcp',
        'version': '1.0.0',
        'description': 'DataDog log search MCP server for triage workflows',
        'available_tools': [
            'search_logs',
            'get_trace_logs',
            'search_business_events',
            'trace_request_flow',
            'test_connection',
            'get_server_info',
            'debug_configuration'
        ]
    }


@mcp.tool
async def debug_configuration() -> Dict[str, Any]:
    """
    Get detailed debugging information about DataDog configuration and credentials.

    Returns:
        Dict containing detailed debugging information for troubleshooting API issues
    """
    import os

    return {
        'datadog_credentials': {
            'api_key_set': bool(os.environ.get('DD_API_KEY')),
            'app_key_set': bool(os.environ.get('DD_APP_KEY')),
            'site': os.environ.get('DD_SITE', 'datadoghq.com')
        },
        'environment_variables': {
            'DD_API_KEY': 'SET' if os.environ.get('DD_API_KEY') else 'NOT_SET',
            'DD_APP_KEY': 'SET' if os.environ.get('DD_APP_KEY') else 'NOT_SET',
            'DD_SITE': os.environ.get('DD_SITE', 'datadoghq.com')
        }
    }


def main():
    """Main entry point for the MCP server."""
    mcp.run()

# Start the server
if __name__ == '__main__':
    main()