class SourcegraphError(Exception):
    """Base exception for all Sourcegraph client and parser errors."""

    pass


class NetworkError(SourcegraphError):
    """Raised when an HTTP transport or connection issue occurs."""

    pass


class ResponseParseError(SourcegraphError):
    """Raised when JSON parsing or dictionary mapping fails due to malformed payloads."""

    pass


class APIError(SourcegraphError):
    """Raised when the Sourcegraph GraphQL backend returns error objects or non-200 responses."""

    pass
