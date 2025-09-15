from typing import Dict, Any

from fastmcp import FastMCP
from .client import DataDogLogsClient
from .filter_config import validate_service_filters, get_service_examples

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
    service: str = None,
    hours: int = 1,
    limit: int = 50,
    cursor: str = None,
    # Common filters (work across all services)
    user_id: int = None,
    tenant_id: int = None,
    status: str = None,
    # Service-specific filters (automatically validated)
    filters: Dict[str, Any] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Search DataDog logs with service-aware filtering.

    Args:
        query: Base DataDog search query (default: 'env:prod')
        service: Service to search (tasmania, meeting, assessment, integration)
        hours: How many hours back to search (default: 1)
        limit: Maximum number of logs to return (default: 50)
        cursor: Pagination cursor for retrieving subsequent pages (optional)
        user_id: Filter by specific user ID (universal)
        tenant_id: Filter by specific tenant ID (universal)
        status: Filter by log status (ERROR, WARN, INFO)
        filters: Service-specific filters. Examples:
            - tasmania: {"space_id": 169183}
            - meeting: {"meeting_id": 136666, "path_id": 12345}
            - assessment: {"assessment_id": 789}
            - integration: {"provider": "zoom"}
        verbose: If True, return all log fields except explicitly blacklisted ones

    Returns:
        Dict containing filtered logs and search metadata

    Examples:
        # Tasmania space filtering
        search_logs(service="tasmania", user_id=281157, filters={"space_id": 169183})

        # Meeting service errors
        search_logs(service="meeting", status="ERROR", filters={"meeting_id": 136666})

        # Cross-service user activity
        search_logs(user_id=279361, hours=24)
    """
    client = get_client()
    time_from = f"now-{hours}h"

    # Extract service-specific filters from filters dict
    service_filters = filters or {}

    # Validate service-specific filters
    if service and service_filters:
        validation_errors = validate_service_filters(service, service_filters)
        if validation_errors:
            examples = get_service_examples(service)
            return {
                "error": "Invalid filters for service",
                "validation_errors": validation_errors,
                "service": service,
                "examples": examples,
            }

    try:
        result = await client.search_logs_with_service_filters(
            query=query,
            time_from=time_from,
            limit=limit,
            cursor=cursor,
            verbose=verbose,
            service=service,
            user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            # Unpack service-specific filters
            meeting_id=service_filters.get("meeting_id"),
            path_id=service_filters.get("path_id"),
            assessment_id=service_filters.get("assessment_id"),
            space_id=service_filters.get("space_id"),
            **{
                k: v
                for k, v in service_filters.items()
                if k not in ["meeting_id", "path_id", "assessment_id", "space_id"]
            },
        )
        return result
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "hours": hours,
            "service": service,
            "filters": filters,
        }


@mcp.tool
async def get_trace_logs(
    trace_id: str, hours: int = 1, cursor: str = None
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
        return {"error": str(e), "trace_id": trace_id, "hours": hours}


@mcp.tool
async def search_business_events(
    event_type: str, service: str = None, hours: int = 24
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
            "error": str(e),
            "event_type": event_type,
            "service": service,
            "hours": hours,
        }


@mcp.tool
async def trace_request_flow(request_id: str, hours: int = 1) -> Dict[str, Any]:
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
        return {"error": str(e), "request_id": request_id, "hours": hours}


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
        "server_name": "torch-datadog-mcp",
        "version": "1.0.0",
        "description": "DataDog log search MCP server for triage workflows",
        "available_tools": [
            "search_logs",
            "get_trace_logs",
            "search_business_events",
            "trace_request_flow",
            "test_connection",
            "get_server_info",
            "debug_configuration",
        ],
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
        "datadog_credentials": {
            "api_key_set": bool(os.environ.get("DD_API_KEY")),
            "app_key_set": bool(os.environ.get("DD_APP_KEY")),
            "site": os.environ.get("DD_SITE", "datadoghq.com"),
        },
        "environment_variables": {
            "DD_API_KEY": "SET" if os.environ.get("DD_API_KEY") else "NOT_SET",
            "DD_APP_KEY": "SET" if os.environ.get("DD_APP_KEY") else "NOT_SET",
            "DD_SITE": os.environ.get("DD_SITE", "datadoghq.com"),
        },
    }


def main():
    """Main entry point for the MCP server."""
    mcp.run()


# Start the server
if __name__ == "__main__":
    main()
