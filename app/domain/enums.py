from enum import StrEnum


class RequestCategory(StrEnum):
    BILLING_ISSUE = "billing_issue"
    ACCOUNT_ACCESS = "account_access"
    INCIDENT_REPORT = "incident_report"
    FEATURE_REQUEST = "feature_request"
    VENDOR_REQUEST = "vendor_request"
    OTHER = "other"


class PriorityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RecommendedTeam(StrEnum):
    BILLING = "billing"
    SUPPORT = "support"
    ENGINEERING = "engineering"
    SUCCESS = "success"
    OPERATIONS = "operations"


class RecommendedAction(StrEnum):
    ROUTE_TO_TEAM = "route_to_team"
    REQUEST_MORE_INFO = "request_more_info"
    DRAFT_REPLY = "draft_reply"
    ESCALATE = "escalate"
    REVIEW_MANUALLY = "review_manually"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"


class IntakeChannel(StrEnum):
    EMAIL = "email"
    WEB_FORM = "web_form"
    CHAT = "chat"
    INTERNAL = "internal"


class CustomerTier(StrEnum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
