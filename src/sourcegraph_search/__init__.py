from sourcegraph_search.client import (
    SourcegraphClient,
    AsyncSourcegraphClient,
    SourcegraphError,
    SourcegraphClientProtocol,
    AsyncSourcegraphClientProtocol,
)


def hello() -> str:
    return "Hello from sourcegraph-search!"


__all__ = [
    "SourcegraphClient",
    "AsyncSourcegraphClient",
    "SourcegraphError",
    "SourcegraphClientProtocol",
    "AsyncSourcegraphClientProtocol",
    "hello",
]
