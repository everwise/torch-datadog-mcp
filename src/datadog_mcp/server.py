from typing import Dict, Any
import uuid
import asyncio

from fastmcp import FastMCP
from cachetools import TTLCache
from .client import DataDogLogsClient
from .filter_config import validate_service_filters, get_service_examples

# Create the MCP server instance
mcp = FastMCP()

_client = None

# TTL cache for preview results (30 second expiration, max 100 entries)
_preview_cache = TTLCache(maxsize=100, ttl=30)


def get_client():
    global _client
    if _client is None:
        try:
            _client = DataDogLogsClient()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DataDog client: {e}")
    return _client


def _cache_preview_result(
    search_params: Dict[str, Any], sample_result: Dict[str, Any]
) -> str:
    """Cache preview result and return cache ID."""
    cache_id = str(uuid.uuid4())
    _preview_cache[cache_id] = {
        "search_params": search_params,
        "sample_result": sample_result,
    }
    return cache_id


def _get_cached_search_params(cache_id: str) -> Dict[str, Any]:
    """Retrieve cached search parameters if still valid."""
    cached_data = _preview_cache.get(cache_id)
    return cached_data["search_params"] if cached_data else None


def _validate_query_safety(
    query: str, hours: int, limit: int, service: str = None
) -> Dict[str, Any]:
    """
    Validate query for potential size issues and provide recommendations.

    Returns dict with 'warnings' and 'recommendations' if issues detected.
    """
    warnings = []
    recommendations = []

    # Check for overly broad queries
    is_broad_query = False

    # Detect broad literal searches (quoted strings without specific filters)
    if '"' in query and not any(
        field in query
        for field in [
            "service:",
            "status:",
            "@user_id:",
            "@meeting_id:",
            "@path_id:",
            "@assessment_id:",
            "@tenant_id:",
            "@trace_id:",
            "@span_id:",
        ]
    ):
        is_broad_query = True
        warnings.append("Literal string search without specific field filters")
        recommendations.append(
            "Add specific field filters like service:meeting or @user_id:123"
        )

    # Check for very generic queries
    if query.strip() in ["env:prod", "*"] and not service:
        is_broad_query = True
        warnings.append("Very generic query without service filter")
        recommendations.append(
            "Specify a service (meeting, tasmania, assessment, integration)"
        )

    # Check time range vs specificity
    if hours > 6 and is_broad_query:
        warnings.append(f"Long time range ({hours}h) with broad query")
        recommendations.append("Reduce time range to 1-2 hours for broad queries")

    # Check high limit with broad query
    if limit > 50 and is_broad_query:
        warnings.append(f"High limit ({limit}) with broad query")
        recommendations.append(
            "Use limit ≤ 50 for broad queries, or add more specific filters"
        )

    # Estimate risk level
    risk_level = "low"
    if len(warnings) >= 2:
        risk_level = "high"
    elif len(warnings) == 1:
        risk_level = "medium"

    if warnings:
        return {
            "has_warnings": True,
            "risk_level": risk_level,
            "warnings": warnings,
            "recommendations": recommendations,
            "suggestion": "Consider using more specific filters to reduce response size and improve performance",
        }

    return {"has_warnings": False}


@mcp.tool
async def preview_search(
    query: str = "env:prod",
    service: str = None,
    hours: int = 24,
    limit: int = 25,
    # Common filters (work across all services)
    user_id: int = None,
    tenant_id: int = None,
    status: str = None,
    # Logical filters (may map to multiple fields with OR conditions)
    actor_email: str = None,
    # Service-specific filters (automatically validated)
    filters: Dict[str, Any] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Preview a DataDog log search to estimate size and count before executing the full query.

    This tool runs a small sample query (limit=5) to estimate the total result size,
    helping prevent accidentally overwhelming responses. Returns a cache_id that can be
    used with search_logs() within 30 seconds to execute the full query efficiently.

    Args:
        Same as search_logs() - all the same filtering parameters

    Returns:
        Dict containing:
        - estimated_count: Approximate number of matching logs
        - estimated_size_mb: Estimated total response size in MB
        - sample_logs: 3 sample log entries for structure preview
        - cache_id: Use this with search_logs(cache_id=...) to execute full query
        - query_warnings: Warnings about potentially problematic queries
        - recommendations: Specific suggestions for improving the query
        - expires_in_seconds: How long the cache_id remains valid (30s)

    Example workflow:
        # Step 1: Preview the query using structured filters
        preview = preview_search(service="meeting", user_id=281157, status="ERROR", hours=2, limit=50)

        # Step 2: Check if it's reasonable
        if preview["estimated_size_mb"] < 1.0 and preview["query_warnings"]["risk_level"] != "high":
            # Step 3: Execute using cache_id
            results = search_logs(cache_id=preview["cache_id"])
        else:
            # Refine query based on recommendations
    """
    client = get_client()
    time_from = f"now-{hours}h"

    # Store original search parameters for caching
    search_params = {
        "query": query,
        "service": service,
        "hours": hours,
        "limit": limit,
        "cursor": None,  # Don't cache cursor-based searches
        "user_id": user_id,
        "tenant_id": tenant_id,
        "status": status,
        "actor_email": actor_email,
        "filters": filters,
        "verbose": verbose,
    }

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

    # Validate query safety
    query_validation = _validate_query_safety(query, hours, limit, service)

    try:
        # Run a small sample query to estimate the full result
        sample_result = await client.search_logs_with_service_filters(
            query=query,
            time_from=time_from,
            limit=5,  # Small sample for estimation
            cursor=None,
            verbose=False,  # Keep sample small
            service=service,
            user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            # Logical filters
            actor_email=actor_email,
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

        # Estimate full query results based on sample
        sample_count = len(sample_result.get("logs", []))
        if sample_count == 0:
            estimated_count = 0
            estimated_size_mb = 0.0
        else:
            # Rough estimation: if we got 5 logs in sample, estimate total
            # This is imprecise but gives a ballpark
            if sample_count < 5:
                # We got fewer than requested, probably close to total
                estimated_count = sample_count
            else:
                # Rough multiplier based on time range and limit
                estimated_count = min(limit * 3, sample_count * (limit // 5))

            # Estimate size based on sample
            sample_size_bytes = sample_result.get("response_size_bytes", 1000)
            estimated_size_bytes = (sample_size_bytes / sample_count) * estimated_count
            estimated_size_mb = estimated_size_bytes / (1024 * 1024)

        # Cache the search parameters for potential full execution
        cache_id = _cache_preview_result(search_params, sample_result)

        result = {
            "estimated_count": estimated_count,
            "estimated_size_mb": round(estimated_size_mb, 2),
            "sample_logs": sample_result.get("logs", [])[:3],  # Show only 3 for preview
            "cache_id": cache_id,
            "expires_in_seconds": 30,
            "original_query_params": {
                "query": query,
                "service": service,
                "hours": hours,
                "limit": limit,
            },
        }

        # Add query validation warnings
        if query_validation.get("has_warnings"):
            result["query_warnings"] = query_validation

        # Add execution recommendation
        if estimated_size_mb > 1.0:
            result["execution_recommendation"] = (
                "CAUTION: Large response expected. Consider more specific filters."
            )
        elif query_validation.get("risk_level") == "high":
            result["execution_recommendation"] = (
                "NOT RECOMMENDED: High-risk query. Please refine filters."
            )
        elif estimated_count > 100:
            result["execution_recommendation"] = (
                "REVIEW: High log count. Consider if this matches your debugging needs."
            )
        else:
            result["execution_recommendation"] = (
                "OK: Reasonable query size. Safe to execute."
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
async def search_logs(
    query: str = "env:prod",
    service: str = None,
    hours: int = 24,
    limit: int = 25,  # Reduced from 50 to be more conservative
    cursor: str = None,
    # Cache parameter for optimized execution after preview
    cache_id: str = None,
    # Common filters (work across all services)
    user_id: int = None,
    tenant_id: int = None,
    status: str = None,
    # Logical filters (may map to multiple fields with OR conditions)
    actor_email: str = None,
    # Service-specific filters (automatically validated)
    filters: Dict[str, Any] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Search DataDog logs with service-aware filtering and automatic response size safeguards.

    RECOMMENDED WORKFLOW: Use preview_search() first, then execute with cache_id for large queries.

    IMPORTANT SAFEGUARDS:
    - Responses are limited to 500KB to prevent LLM context overflow
    - Individual log entries are capped at 10KB with large payloads removed
    - Query validation warns about overly broad searches
    - Large request/response data is automatically truncated with summaries

    Args:
        query: Base DataDog search query (default: 'env:prod')
        service: Service to search (tasmania, meeting, assessment, integration) - RECOMMENDED
        hours: How many hours back to search (default: 1, max recommended: 6 for broad queries)
        limit: Maximum number of logs to return (default: 25, max recommended: 50)
        cursor: Pagination cursor for retrieving subsequent pages (optional)
        cache_id: Cache ID from preview_search() for optimized execution (30s TTL)
        user_id: Filter by specific user ID (universal) - HIGHLY RECOMMENDED
        tenant_id: Filter by specific tenant ID (universal)
        status: Filter by log status (ERROR, WARN, INFO) - RECOMMENDED for faster searches
        filters: Service-specific filters. Examples:
            - tasmania: {"space_id": 169183}
            - meeting: {"meeting_id": 136666, "path_id": 12345}
            - assessment: {"assessment_id": 789}
            - integration: {"provider": "zoom"}
        verbose: If True, return all log fields (with size limits) instead of just valuable ones

    Returns:
        Dict containing:
        - logs: Filtered and size-limited log entries
        - response_size_bytes: Actual response size
        - truncated: True if response was cut off due to size limits
        - query_warnings: Warnings about potentially problematic queries
        - from_cache: True if executed from preview cache
        - Standard metadata (total_count, time_range, etc.)

    BEST PRACTICES:
        # RECOMMENDED: Preview first for large queries
        preview = preview_search(query='env:prod "130361"', hours=24, limit=100)
        if preview["execution_recommendation"] == "OK":
            results = search_logs(cache_id=preview["cache_id"])

        # Direct execution for small, specific queries
        search_logs(service="meeting", user_id=281157, status="ERROR", hours=2)
    """
    client = get_client()

    # Check if this is a cached execution from preview_search
    from_cache = False
    if cache_id:
        cached_params = _get_cached_search_params(cache_id)
        if cached_params:
            # Use cached parameters instead of provided ones
            query = cached_params["query"]
            service = cached_params["service"]
            hours = cached_params["hours"]
            limit = cached_params["limit"]
            user_id = cached_params["user_id"]
            tenant_id = cached_params["tenant_id"]
            status = cached_params["status"]
            actor_email = cached_params["actor_email"]
            filters = cached_params["filters"]
            verbose = cached_params["verbose"]
            from_cache = True
        else:
            return {
                "error": "Cache ID expired or invalid",
                "cache_id": cache_id,
                "suggestion": "Use preview_search() to generate a new cache_id, or provide search parameters directly",
            }

    time_from = f"now-{hours}h"

    # Extract service-specific filters from filters dict
    service_filters = filters or {}

    # Skip validation for cached queries (already validated in preview)
    query_validation = {"has_warnings": False}
    if not from_cache:
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

        # Validate query safety and provide warnings for potentially problematic queries
        query_validation = _validate_query_safety(query, hours, limit, service)

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
            # Logical filters
            actor_email=actor_email,
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

        # Add query validation warnings to the result (skip for cached queries as they were already validated)
        if not from_cache and query_validation.get("has_warnings"):
            result["query_warnings"] = query_validation

        # Add cache indicator
        result["from_cache"] = from_cache
        if from_cache:
            result["cache_note"] = (
                "Executed using cached parameters from preview_search()"
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
