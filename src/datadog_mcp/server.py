"""DataDog MCP server for log search and monitoring integration."""

from typing import Dict, Any, Optional

from fastmcp import FastMCP
from .client import DataDogLogsClient

# Create the MCP server
mcp = FastMCP("DataDog Logs Server")

# Initialize DataDog client
_client = None


def get_client() -> DataDogLogsClient:
    """Get or create DataDog client instance."""
    global _client
    if _client is None:
        try:
            _client = DataDogLogsClient()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DataDog client: {e}")
    return _client


@mcp.tool
async def search_logs(
    query: str,
    hours: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Search DataDog logs with a custom query.

    Args:
        query: DataDog search query (e.g., 'env:prod service:meeting status:ERROR')
        hours: How many hours back to search (default: 1)
        limit: Maximum number of logs to return (default: 50)

    Returns:
        Dict containing logs and search metadata
    """
    client = get_client()
    time_from = f"now-{hours}h"

    try:
        result = await client.search_logs(
            query=query,
            time_from=time_from,
            limit=limit
        )
        return result
    except Exception as e:
        return {
            'error': str(e),
            'query': query,
            'hours': hours
        }


@mcp.tool
async def search_meeting_logs(
    meeting_id: int,
    hours: int = 168
) -> Dict[str, Any]:
    """
    Search for all logs related to a specific meeting.

    Args:
        meeting_id: The meeting ID to search for
        hours: How many hours back to search (default: 168 = 7 days)

    Returns:
        Dict containing meeting-related logs
    """
    client = get_client()

    try:
        result = await client.search_meeting_logs(meeting_id, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'meeting_id': meeting_id,
            'hours': hours
        }


@mcp.tool
async def search_user_logs(
    user_id: int,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Search for all logs related to a specific user.

    Args:
        user_id: The user ID to search for
        hours: How many hours back to search (default: 24)

    Returns:
        Dict containing user-related logs
    """
    client = get_client()

    try:
        result = await client.search_user_logs(user_id, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'user_id': user_id,
            'hours': hours
        }


@mcp.tool
async def search_webhook_events(
    meeting_id: int,
    provider: Optional[str] = None,
    hours: int = 168
) -> Dict[str, Any]:
    """
    Search for webhook events related to a meeting.

    Args:
        meeting_id: The meeting ID to search for
        provider: Optional provider filter ('zoom', 'whereby', or None for all)
        hours: How many hours back to search (default: 168 = 7 days)

    Returns:
        Dict containing webhook events for the meeting
    """
    client = get_client()

    try:
        result = await client.search_webhook_events(meeting_id, provider, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'meeting_id': meeting_id,
            'provider': provider,
            'hours': hours
        }


@mcp.tool
async def search_errors(
    service: Optional[str] = None,
    hours: int = 2
) -> Dict[str, Any]:
    """
    Search for recent errors across services.

    Args:
        service: Optional service filter (e.g., 'meeting', 'integration')
        hours: How many hours back to search (default: 2)

    Returns:
        Dict containing recent error logs
    """
    client = get_client()

    try:
        result = await client.search_errors(service, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'service': service,
            'hours': hours
        }


@mcp.tool
async def search_trace(
    trace_id: str,
    hours: int = 1
) -> Dict[str, Any]:
    """
    Search for all logs in a specific APM trace.

    Args:
        trace_id: The trace ID to search for
        hours: How many hours back to search (default: 1)

    Returns:
        Dict containing all logs for the trace
    """
    client = get_client()

    try:
        result = await client.search_trace(trace_id, hours)
        return result
    except Exception as e:
        return {
            'error': str(e),
            'trace_id': trace_id,
            'hours': hours
        }


@mcp.tool
async def test_connection() -> Dict[str, Any]:
    """
    Test the DataDog API connection and configuration.

    Returns:
        Dict containing connection status and test results
    """
    try:
        client = get_client()
        result = await client.test_connection()
        return result
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to test connection: {str(e)}'
        }


@mcp.tool
async def get_server_info() -> Dict[str, Any]:
    """
    Get information about the DataDog MCP server configuration.

    Returns:
        Dict containing server information and configuration
    """
    import os

    return {
        'server_name': 'DataDog Logs Server',
        'version': '0.1.0',
        'datadog_site': os.environ.get('DD_SITE', 'datadoghq.com'),
        'api_key_configured': bool(os.environ.get('DD_API_KEY')),
        'app_key_configured': bool(os.environ.get('DD_APP_KEY')),
        'available_tools': [
            'search_logs',
            'search_meeting_logs',
            'search_user_logs',
            'search_webhook_events',
            'search_errors',
            'search_trace',
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
    import sys

    try:
        client = get_client()
        debug_info = getattr(client, 'debug_info', {})

        api_key = os.environ.get('DD_API_KEY')
        app_key = os.environ.get('DD_APP_KEY')
        site = os.environ.get('DD_SITE', 'datadoghq.com')

        return {
            'status': 'success',
            'direct_environment_auth': {
                'api_key_present': bool(api_key),
                'api_key_prefix': api_key[:8] + '...' if api_key else None,
                'app_key_present': bool(app_key),
                'app_key_prefix': app_key[:8] + '...' if app_key else None,
                'site': site
            },
            'environment_variables': {
                'DD_API_KEY': bool(os.environ.get('DD_API_KEY')),
                'DD_APP_KEY': bool(os.environ.get('DD_APP_KEY')),
                'DD_SITE': os.environ.get('DD_SITE')
            },
            'client_debug_info': debug_info,
            'python_version': sys.version,
            'datadog_client_available': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'environment_accessible': False,
            'datadog_client_available': False
        }


def main():
    """Main entry point for the DataDog MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()