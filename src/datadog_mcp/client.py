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
        sort: str = "-timestamp",
        cursor: Optional[str] = None
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
        page_params = {"limit": limit}
        if cursor:
            page_params["cursor"] = cursor

        body = LogsListRequest(
            filter=LogsQueryFilter(
                query=query,
                **{"from": time_from, "to": time_to},
            ),
            sort=LogsSort.TIMESTAMP_DESCENDING if sort == "-timestamp" else LogsSort.TIMESTAMP_ASCENDING,
            page=LogsListRequestPage(**page_params),
        )

        try:
            response = self.logs_api.list_logs(body=body)

            # Format the logs for JSON serialization
            formatted_logs = []
            for log in response.data:
                formatted_logs.append(self._format_log_entry(log))

            # Extract pagination info
            next_cursor = None
            if hasattr(response, 'meta') and hasattr(response.meta, 'page'):
                next_cursor = getattr(response.meta.page, 'after', None)

            result = {
                'logs': formatted_logs,
                'total_count': len(formatted_logs),
                'query': query,
                'time_range': f"{time_from} to {time_to}",
                'elapsed_ms': getattr(response.meta, 'elapsed', None) if hasattr(response, 'meta') else None
            }

            # Only include cursor info if there are more results
            if next_cursor:
                result['next_cursor'] = next_cursor
                result['has_more'] = True
            else:
                result['has_more'] = False

            return result
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

    # Removed redundant search methods - use main search_logs with filtering parameters

    async def get_trace_logs(
        self,
        trace_id: str,
        hours: int = 1,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all logs across ALL services for a given APM trace ID with pagination support."""
        query = f"env:prod @dd.trace_id:{trace_id}"
        time_from = f"now-{hours}h"

        return await self.search_logs(
            query=query,
            time_from=time_from,
            limit=200,
            cursor=cursor
        )

    # Removed redundant search methods - use main search_logs with filtering parameters

    async def search_business_events(
        self,
        event_type: str,
        service: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Search for business events across services."""
        query_parts = ["env:prod"]

        if service:
            query_parts.append(f"service:{service}")

        # Add event type patterns based on observed log structures
        if "meeting" in event_type:
            query_parts.append(f"@event:{event_type}")
        elif "webhook" in event_type:
            query_parts.append(f"@payload.event:{event_type}")
        else:
            query_parts.append(f'"{event_type}"')

        query = " AND ".join(query_parts)
        time_from = f"now-{hours}h"

        return await self.search_logs(query, time_from=time_from, limit=100)

    # Removed redundant search methods - use main search_logs with filtering parameters

    # Removed health check method - not needed for triage workflows

    async def trace_request_flow(
        self,
        request_id: str,
        hours: int = 1
    ) -> Dict[str, Any]:
        """Track a request across multiple services using request_id or correlation IDs."""
        # Try different request ID patterns found in logs
        queries = [
            f"env:prod @request_id:{request_id}",
            f"env:prod @lambda.request_id:{request_id}",
            f"env:prod @context.request.headers.X-Amzn-Trace-Id:{request_id}"
        ]

        time_from = f"now-{hours}h"
        all_logs = []
        services_involved = set()

        for query in queries:
            result = await self.search_logs(query, time_from=time_from, limit=200)
            if result.get('logs'):
                all_logs.extend(result['logs'])
                for log in result['logs']:
                    services_involved.add(log.get('service', 'unknown'))

        # Sort by timestamp for flow visualization
        all_logs.sort(key=lambda x: x.get('timestamp', ''))

        return {
            'logs': all_logs,
            'total_count': len(all_logs),
            'request_id': request_id,
            'services_involved': list(services_involved),
            'time_range': f"now-{hours}h to now",
            'flow_summary': {
                'first_log': all_logs[0] if all_logs else None,
                'last_log': all_logs[-1] if all_logs else None,
                'duration_ms': None  # Could calculate if timestamps are available
            }
        }

    def _format_log_entry(self, log_entry: Any) -> Dict[str, Any]:
        """Format a log entry for JSON serialization, filtering out noise for triage."""
        attributes = log_entry.attributes

        formatted = {
            'timestamp': getattr(attributes, 'timestamp', None),
            'message': getattr(attributes, 'message', ''),
            'status': getattr(attributes, 'status', ''),
            'service': getattr(attributes, 'service', ''),
            'host': getattr(attributes, 'host', ''),
        }

        # Add custom attributes if they exist, but filter out noise
        if hasattr(attributes, 'attributes') and attributes.attributes:
            custom_attrs = dict(attributes.attributes)

            # Fields valuable for triage (keep these)
            valuable_fields = [
                'user_id', 'tenant_id', 'meeting_id', 'path_id', 'assessment_id',
                'trace_id', 'span_id', 'execution_uuid', 'duration_ms', 'duration',
                'status_code', 'error_code', 'error_message', 'level',
                'lambda', 'dd', 'env', 'version'
            ]

            # Extract valuable fields to top level
            for field in valuable_fields:
                if field in custom_attrs:
                    formatted[field] = custom_attrs[field]

            # Clean context data - keep only useful parts
            if 'context' in custom_attrs:
                context = custom_attrs['context']
                if isinstance(context, dict):
                    clean_context = {}
                    if 'request' in context:
                        request = context['request']
                        if isinstance(request, dict):
                            clean_request = {
                                'method': request.get('method'),
                                'path': request.get('path'),
                                'scheme': request.get('scheme')
                            }
                            # Preserve request.data if present
                            if 'data' in request:
                                clean_request['data'] = request['data']
                            clean_context['request'] = clean_request
                    if 'response' in context:
                        response = context['response']
                        if isinstance(response, dict):
                            clean_response = {
                                'status_code': response.get('status_code')
                            }
                            # Preserve response.data if present
                            if 'data' in response:
                                clean_response['data'] = response['data']
                            clean_context['response'] = clean_response
                    if clean_context:
                        formatted['context'] = clean_context

            # Remove noisy network data
            if 'network' in custom_attrs:
                del custom_attrs['network']

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