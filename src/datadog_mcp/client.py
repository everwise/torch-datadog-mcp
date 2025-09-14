"""DataDog Logs API client for MCP server."""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.logs_api import LogsApi
    from datadog_api_client.v2.model.logs_list_request import LogsListRequest
    from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
    from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
    from datadog_api_client.v2.model.logs_sort import LogsSort
except ImportError as e:
    raise ImportError("datadog-api-client is required: pip install datadog-api-client") from e


class DataDogLogsClient:
    """DataDog Logs API client for production debugging."""

    def __init__(self):
        """Initialize the DataDog client with direct environment variable authentication."""
        # Check environment variables directly - don't go through pydantic
        api_key = os.environ.get('DD_API_KEY')
        app_key = os.environ.get('DD_APP_KEY')
        site = os.environ.get('DD_SITE', 'datadoghq.com')

        if not api_key:
            raise ValueError("""
            DD_API_KEY not found in environment variables.

            DataDog requires both an API key and Application key for log searches:
            1. DD_API_KEY - Your DataDog API key (for authentication)
            2. DD_APP_KEY - Your DataDog Application key (for authorization)

            These must be set as environment variables in your claude.json configuration.
            """)

        if not app_key:
            raise ValueError("DD_APP_KEY not found in environment variables")

        # Store debug info for troubleshooting
        self.debug_info = {
            'api_key_present': bool(api_key),
            'api_key_prefix': api_key[:8] + '...' if api_key else None,
            'app_key_present': bool(app_key),
            'app_key_prefix': app_key[:8] + '...' if app_key else None,
            'site': site,
            'auth_source': 'direct_environment_variables',
            'pydantic_bypassed': True
        }

        # DataDog Configuration() will read from environment variables
        configuration = Configuration()

        self.api_client = ApiClient(configuration)
        self.logs_api = LogsApi(self.api_client)

    async def search_logs(
        self,
        query: str = "*",
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = 50,
        sort: str = "-timestamp"
    ) -> Dict[str, Any]:
        """
        Search DataDog logs with the given query.

        Args:
            query: Search query following DataDog log search syntax
            time_from: Start time (ISO format or 'now-1h' syntax). Default: now-1h
            time_to: End time (ISO format or 'now' syntax). Default: now
            limit: Maximum number of logs to return
            sort: Sort order ('timestamp' or '-timestamp')

        Returns:
            Dict containing logs and metadata
        """
        if time_from is None:
            time_from = "now-1h"
        if time_to is None:
            time_to = "now"

        # Build the request
        body = LogsListRequest(
            filter=LogsQueryFilter(
                query=query,
                **{"from": time_from, "to": time_to},
            ),
            sort=LogsSort.TIMESTAMP_DESCENDING if sort == "-timestamp" else LogsSort.TIMESTAMP_ASCENDING,
            page=LogsListRequestPage(limit=limit),
        )

        try:
            response = self.logs_api.list_logs(body=body)

            # Format the logs for JSON serialization
            formatted_logs = []
            for log in response.data:
                formatted_logs.append(self._format_log_entry(log))

            return {
                'logs': formatted_logs,
                'total_count': len(formatted_logs),
                'query': query,
                'time_range': f"{time_from} to {time_to}",
                'elapsed_ms': getattr(response.meta, 'elapsed', None) if hasattr(response, 'meta') else None
            }
        except Exception as e:
            error_details = {
                'logs': [],
                'error': str(e),
                'error_type': type(e).__name__,
                'query': query,
                'time_range': f"{time_from} to {time_to}",
                'debug_info': getattr(self, 'debug_info', None)
            }

            # Add detailed HTTP error information if available
            if hasattr(e, 'status'):
                error_details['http_status'] = e.status
            if hasattr(e, 'reason'):
                error_details['http_reason'] = e.reason
            if hasattr(e, 'body'):
                error_details['http_body'] = e.body
            if hasattr(e, 'headers'):
                error_details['http_headers'] = dict(e.headers) if e.headers else None

            return error_details

    async def search_meeting_logs(
        self,
        meeting_id: int,
        hours: int = 168
    ) -> Dict[str, Any]:
        """Search for all logs related to a specific meeting."""
        query = f"env:prod service:meeting @meeting_id:{meeting_id}"
        time_from = f"now-{hours}h"

        return await self.search_logs(query, time_from=time_from, limit=100)

    async def search_user_logs(
        self,
        user_id: int,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Search for all logs related to a specific user."""
        query = f"env:prod service:meeting @user_id:{user_id}"
        time_from = f"now-{hours}h"

        return await self.search_logs(query, time_from=time_from, limit=100)

    async def search_webhook_events(
        self,
        meeting_id: int,
        provider: Optional[str] = None,
        hours: int = 168
    ) -> Dict[str, Any]:
        """Search for webhook events related to a meeting."""
        time_from = f"now-{hours}h"

        # Search multiple patterns based on provider
        queries = []
        if not provider or provider.lower() == "whereby":
            queries.append(f"env:prod service:integration @request_identifiers.resource_id:{meeting_id}")
        if not provider or provider.lower() == "zoom":
            queries.append(f"env:prod service:integration @payload.payload.object.id:{meeting_id}")

        all_logs = []
        for query in queries:
            result = await self.search_logs(query, time_from=time_from, limit=50)
            if result.get('logs'):
                all_logs.extend(result['logs'])

        return {
            'logs': all_logs,
            'total_count': len(all_logs),
            'meeting_id': meeting_id,
            'provider': provider or 'all',
            'time_range': f"now-{hours}h to now",
            'search_patterns': queries
        }

    async def search_errors(
        self,
        service: Optional[str] = None,
        hours: int = 2
    ) -> Dict[str, Any]:
        """Search for recent errors across services."""
        query_parts = ["env:prod", "status:ERROR"]

        if service:
            query_parts.append(f"service:{service}")

        query = " AND ".join(query_parts)
        time_from = f"now-{hours}h"

        return await self.search_logs(query, time_from=time_from, limit=100)

    async def search_trace(
        self,
        trace_id: str,
        hours: int = 1
    ) -> Dict[str, Any]:
        """Search for all logs in a specific APM trace."""
        # Try different trace ID formats
        queries = [
            f"env:prod @dd.trace_id:{trace_id}",
            f"env:prod @trace_id:{trace_id}",
            f"env:prod dd.trace_id:{trace_id}"
        ]

        time_from = f"now-{hours}h"
        all_logs = []

        for query in queries:
            result = await self.search_logs(query, time_from=time_from, limit=200)
            if result.get('logs'):
                all_logs.extend(result['logs'])

        return {
            'logs': all_logs,
            'total_count': len(all_logs),
            'trace_id': trace_id,
            'time_range': f"now-{hours}h to now",
            'query_patterns_tried': queries
        }

    def _format_log_entry(self, log_entry: Any) -> Dict[str, Any]:
        """Format a log entry for JSON serialization."""
        attributes = log_entry.attributes

        formatted = {
            'timestamp': getattr(attributes, 'timestamp', None),
            'message': getattr(attributes, 'message', ''),
            'status': getattr(attributes, 'status', ''),
            'service': getattr(attributes, 'service', ''),
            'host': getattr(attributes, 'host', ''),
            'tags': getattr(attributes, 'tags', []),
        }

        # Add custom attributes if they exist
        if hasattr(attributes, 'attributes') and attributes.attributes:
            custom_attrs = dict(attributes.attributes)

            # Extract commonly used fields to top level
            interesting_attrs = ['meeting_id', 'user_id', 'trace_id', 'span_id', 'error_code', 'error_message']
            for attr in interesting_attrs:
                if attr in custom_attrs:
                    formatted[attr] = custom_attrs[attr]

            formatted['custom_attributes'] = custom_attrs

        return formatted

    async def test_connection(self) -> Dict[str, Any]:
        """Test DataDog API connection with detailed debugging."""
        try:
            result = await self.search_logs("env:prod", limit=1)

            if result.get('error'):
                return {
                    'status': 'error',
                    'message': f"API test failed: {result['error']}",
                    'error_details': result,
                    'debug_info': getattr(self, 'debug_info', None),
                    'test_query': 'env:prod',
                    'credentials_loaded': {
                        'api_key': bool(os.environ.get('DD_API_KEY')),
                        'app_key': bool(os.environ.get('DD_APP_KEY')),
                        'site': os.environ.get('DD_SITE', 'datadoghq.com')
                    }
                }
            else:
                return {
                    'status': 'success',
                    'message': 'DataDog API connection successful',
                    'test_logs_found': result.get('total_count', 0),
                    'debug_info': getattr(self, 'debug_info', None)
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': f"Connection test failed: {str(e)}",
                'error_type': type(e).__name__,
                'debug_info': getattr(self, 'debug_info', None),
                'credentials_loaded': {
                    'api_key': bool(os.environ.get('DD_API_KEY')),
                    'app_key': bool(os.environ.get('DD_APP_KEY')),
                    'site': os.environ.get('DD_SITE', 'datadoghq.com')
                }
            }