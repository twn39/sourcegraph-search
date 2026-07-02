from sourcegraph_search.client import (
    SourcegraphClient,
    AsyncSourcegraphClient,
    SourcegraphError,
    NetworkError,
    ResponseParseError,
    APIError,
    SourcegraphClientProtocol,
    AsyncSourcegraphClientProtocol,
)


def hello() -> str:
    return "Hello from sourcegraph-search!"


__all__ = [
    "SourcegraphClient",
    "AsyncSourcegraphClient",
    "SourcegraphError",
    "NetworkError",
    "ResponseParseError",
    "APIError",
    "SourcegraphClientProtocol",
    "AsyncSourcegraphClientProtocol",
    "hello",
]
