from sourcegraph_search.client import SourcegraphClient, SourcegraphError

def hello() -> str:
    return "Hello from sourcegraph-search!"

__all__ = ["SourcegraphClient", "SourcegraphError", "hello"]
