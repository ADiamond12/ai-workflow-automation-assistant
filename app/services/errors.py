class RequestNotFoundError(Exception):
    """Raised when a workflow request cannot be found."""


class WorkflowProviderError(Exception):
    """Raised when the workflow provider fails without an active fallback."""


class WorkflowProviderUnavailableError(WorkflowProviderError):
    """Raised when the selected provider is unavailable."""


class WorkflowProviderResponseError(WorkflowProviderError):
    """Raised when the provider returns malformed or refused output."""
