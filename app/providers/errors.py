class ProviderError(Exception):
    """Base exception for provider execution failures."""


class ProviderUnavailableError(ProviderError):
    """Raised when the selected provider cannot be initialized or reached."""


class ProviderResponseError(ProviderError):
    """Raised when the provider returns malformed or unusable output."""
