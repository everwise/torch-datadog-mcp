"""
Service-specific filter configuration for DataDog log queries.

This module defines how different services structure their log data and
what filters are available for querying. Each service has its own set of
filter mappings that correspond to DataDog query syntax.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ServiceConfig:
    """Configuration for a specific service's filter mappings."""

    # Logical filter mappings (each key maps to list of possible fields for OR conditions)
    logical_filters: Dict[str, List[str]]
    # Health check and other paths to exclude
    exclude_paths: List[str]


# Service-specific filter configurations
SERVICE_FILTERS: Dict[str, ServiceConfig] = {
    "tasmania": ServiceConfig(
        logical_filters={
            "user_id": ["@context.current_user_id", "@context.params.user_id"],
            "tenant_id": ["@context.current_tenant_id"],
            "space_id": ["@context.path"],  # Special handling for path patterns
            "actor_email": [
                "@statement.actor.mbox",
                "@context.request.data.actor.mbox",
            ],
        },
        exclude_paths=['"/api/v1/health"', '"/api/v1/pusher/auth"'],
    ),
    "meeting": ServiceConfig(
        logical_filters={
            "user_id": ["@user_id"],
            "tenant_id": ["@tenant_id"],
            "meeting_id": ["@meeting_id"],
            "path_id": ["@context.params.notifiable_id"],
            "actor_email": ["@events.actor.mbox"],
        },
        exclude_paths=['"/api/v1/health"'],
    ),
    "assessment": ServiceConfig(
        logical_filters={
            "user_id": ["@user_id"],
            "tenant_id": ["@tenant_id"],
            "assessment_id": ["@assessment_id"],
        },
        exclude_paths=['"/api/v1/health"'],
    ),
    "integration": ServiceConfig(
        logical_filters={
            "user_id": ["@user_id"],
            "tenant_id": ["@tenant_id"],
            "meeting_id": ["@meeting_id"],
            "provider": ["@provider"],
        },
        exclude_paths=['"/api/v1/health"'],
    ),
}


def build_service_filters(
    service: Optional[str] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    meeting_id: Optional[int] = None,
    path_id: Optional[int] = None,
    assessment_id: Optional[int] = None,
    space_id: Optional[int] = None,
    status: Optional[str] = None,
    # Logical filters that may map to multiple fields
    actor_email: Optional[str] = None,
    **kwargs,
) -> List[str]:
    """
    Build DataDog query filters based on service configuration.

    Args:
        service: Service name for service-specific filtering
        user_id: Filter by user ID (creates OR condition for all user ID fields)
        tenant_id: Filter by tenant ID
        meeting_id: Filter by meeting ID
        path_id: Filter by path ID (or notifiable_id for meeting service)
        assessment_id: Filter by assessment ID
        space_id: Filter by space ID (tasmania specific)
        status: Filter by log status
        actor_email: Filter by actor email (creates OR condition for all email fields)
        **kwargs: Additional service-specific filters

    Returns:
        List of filter strings for DataDog query
    """
    filters = []
    config = SERVICE_FILTERS.get(service) if service else None

    # Add health check exclusions based on service config
    if config:
        for exclude_path in config.exclude_paths:
            filters.append(f"-@context.path:{exclude_path}")
    else:
        filters.append("-@path:*/health")  # Default health check exclusion

    # Add service filter
    if service:
        filters.append(f"service:{service}")

    # Add status filter
    if status:
        filters.append(f"status:{status}")

    # Build service-specific filters
    filter_values = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "meeting_id": meeting_id,
        "path_id": path_id,
        "assessment_id": assessment_id,
        "space_id": space_id,
        "actor_email": actor_email,
    }

    for filter_name, value in filter_values.items():
        if value is not None:
            if config and filter_name in config.logical_filters:
                fields = config.logical_filters[filter_name]
                if len(fields) == 1:
                    # Single field - no OR needed
                    field = fields[0]
                    if filter_name == "space_id":
                        # Special handling for space_id path filtering
                        filters.append(f"{field}:/api/v1/spaces/{value}*")
                    else:
                        filters.append(f"{field}:{value}")
                else:
                    # Multiple fields - create OR condition
                    or_conditions = []
                    for field in fields:
                        if filter_name == "space_id":
                            or_conditions.append(f"{field}:/api/v1/spaces/{value}*")
                        else:
                            or_conditions.append(f"{field}:{value}")
                    filters.append(f"({' OR '.join(or_conditions)})")
            else:
                # Fallback to default field mapping
                filters.append(f"@{filter_name}:{value}")

    # Handle additional filters from kwargs
    for key, value in kwargs.items():
        if value is not None:
            filters.append(f"@{key}:{value}")

    return filters


def get_service_config(service: str) -> Optional[ServiceConfig]:
    """Get configuration for a specific service."""
    return SERVICE_FILTERS.get(service)


def get_available_filters(service: Optional[str] = None) -> Dict[str, str]:
    """Get available filters for a service."""
    config = SERVICE_FILTERS.get(service) if service else None
    if not config:
        return {
            "user_id": "Filter by user ID",
            "tenant_id": "Filter by tenant ID",
            "meeting_id": "Filter by meeting ID",
            "path_id": "Filter by path ID",
            "assessment_id": "Filter by assessment ID",
            "actor_email": "Filter by actor email",
            "status": "Filter by log status",
        }

    return {
        key.replace("_", " ").title(): f"Filter by {key.replace('_', ' ')}"
        for key in config.logical_filters.keys()
    }


def validate_service_filters(
    service: Optional[str], filters: Dict[str, Any]
) -> Dict[str, str]:
    """
    Validate that filters are appropriate for the given service.

    Args:
        service: Service name
        filters: Dict of filter key-value pairs

    Returns:
        Dict of validation errors (empty if all valid)
    """
    if not service or not filters:
        return {}

    config = SERVICE_FILTERS.get(service)
    if not config:
        return {
            "service": f"Unknown service '{service}'. Supported: {list(SERVICE_FILTERS.keys())}"
        }

    errors = {}
    valid_filters = set(config.logical_filters.keys())

    for filter_name in filters.keys():
        if filter_name not in valid_filters:
            errors[filter_name] = (
                f"Filter '{filter_name}' not supported for service '{service}'. Available: {list(valid_filters)}"
            )

    return errors


def get_service_examples(service: str) -> Dict[str, Any]:
    """Get example filter usage for a service."""
    examples = {
        "tasmania": {
            "user_id": 214413,
            "tenant_id": 140,
            "space_id": 168565,
            "actor_email": "user@example.com",
            "description": "Filter by current user, tenant, space ID, or actor email",
        },
        "meeting": {
            "meeting_id": 136666,
            "path_id": 12345,
            "actor_email": "user@example.com",
            "description": "Filter by meeting, learning path, or actor email",
        },
        "assessment": {"assessment_id": 789, "description": "Filter by assessment ID"},
        "integration": {
            "provider": "zoom",
            "meeting_id": 136666,
            "description": "Filter by integration provider",
        },
    }
    return examples.get(service, {})


def list_supported_services() -> List[str]:
    """List all supported services."""
    return list(SERVICE_FILTERS.keys())
