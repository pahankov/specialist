"""API changelog endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/changelog")
async def get_changelog():
    """Get API changelog.
    
    Returns version history with features, fixes, and breaking changes.
    """
    return {
        "current_version": "1.2.0",
        "base_url": "/api/v1",
        "entries": [
            {
                "version": "1.2.0",
                "date": "2026-09-24",
                "type": "feature",
                "title": "Performance & Architecture",
                "changes": [
                    {
                        "type": "feature",
                        "description": "Redis caching for dashboard statistics (5-min TTL)",
                        "impact": "significantly faster dashboard loads"
                    },
                    {
                        "type": "feature",
                        "description": "Background task queue (RQ) for heavy exports",
                        "impact": "non-blocking CSV generation"
                    },
                    {
                        "type": "feature",
                        "description": "Paginated responses with total count",
                        "impact": "better frontend pagination support"
                    },
                    {
                        "type": "feature",
                        "description": "Enhanced health check with DB and cache verification",
                        "impact": "better monitoring and alerting"
                    },
                    {
                        "type": "improvement",
                        "description": "Improved OpenAPI documentation with request examples",
                        "impact": "easier API integration"
                    }
                ]
            },
            {
                "version": "1.1.0",
                "date": "2026-09-15",
                "type": "feature",
                "title": "Admin Panel Enhancements",
                "changes": [
                    {
                        "type": "feature",
                        "description": "Superadmin master management (CRUD, suspend, admin toggle)",
                        "impact": "full control over master accounts"
                    },
                    {
                        "type": "feature",
                        "description": "Audit logs for all admin actions",
                        "impact": "full accountability and compliance"
                    },
                    {
                        "type": "feature",
                        "description": "Blocked slots management",
                        "impact": "masters can block unavailable time"
                    },
                    {
                        "type": "improvement",
                        "description": "No-show tracking with client counter",
                        "impact": "better attendance analytics"
                    }
                ]
            },
            {
                "version": "1.0.0",
                "date": "2026-09-01",
                "type": "release",
                "title": "Initial Release",
                "changes": [
                    {
                        "type": "feature",
                        "description": "Client self-service booking",
                        "impact": "clients can book appointments online"
                    },
                    {
                        "type": "feature",
                        "description": "Master dashboard with statistics",
                        "impact": "masters can track their appointments"
                    },
                    {
                        "type": "feature",
                        "description": "OTP-based authentication for clients",
                        "impact": "passwordless login via phone"
                    },
                    {
                        "type": "feature",
                        "description": "Service catalog management",
                        "impact": "masters can manage services and pricing"
                    },
                    {
                        "type": "feature",
                        "description": "Working hours and schedule management",
                        "impact": "masters can set availability"
                    }
                ]
            }
        ]
    }
