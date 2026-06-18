import os
import json
from typing import Any, Dict, List, Optional
import typer
from sourcegraph_search.client import SourcegraphClient, SourcegraphError

app = typer.Typer(
    help="CLI tool to search code and navigate definitions/references via Sourcegraph's GraphQL API.",
    add_completion=False,
)

def version_callback(value: bool):
    if value:
        try:
            import importlib.metadata
            version = importlib.metadata.version("sourcegraph-search")
        except Exception:
            version = "0.1.0"
        typer.echo(f"sourcegraph-search version {version}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    ),
):
    """Sourcegraph Search and Code Intelligence CLI."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

def _get_client(endpoint: str, token: Optional[str], timeout: int) -> SourcegraphClient:
    api_token = token or os.environ.get("SOURCEGRAPH_TOKEN") or os.environ.get("SOURCEGRAPH_API_TOKEN")
    return SourcegraphClient(endpoint=endpoint, token=api_token, timeout=float(timeout))

@app.command(name="search")
def search_cmd(
    query: str = typer.Argument(
        ...,
        help="The Sourcegraph search query (e.g. 'repo:github.com/charmbracelet/crush NewSourcegraphTool')"
    ),
    count: int = typer.Option(
        10,
        "--count",
        "-n",
        help="Number of results to return (default: 10, max: 20)"
    ),
    context_window: int = typer.Option(
        10,
        "--context-window",
        "-c",
        help="Number of lines of context to display around each match"
    ),
    endpoint: str = typer.Option(
        "https://sourcegraph.com",
        "--endpoint",
        help="Sourcegraph instance URL"
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Sourcegraph API token (overrides SOURCEGRAPH_TOKEN or SOURCEGRAPH_API_TOKEN env variables)"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output raw JSON results instead of formatted markdown"
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Request timeout in seconds"
    ),
):
    """Search code, symbols, commits, and repositories."""
    if count <= 0:
        count = 10
    elif count > 20:
        count = 20

    try:
        client = _get_client(endpoint, token, timeout)
        result_data = client.search(query)
        
        if json_output:
            typer.echo(json.dumps(result_data, indent=2))
        else:
            formatted = client.format_results(
                result_data,
                context_window=context_window,
                max_results=count
            )
            typer.echo(formatted)
    except SourcegraphError as err:
        typer.secho(f"Error: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command(name="fetch")
def fetch_cmd(
    repo: str = typer.Argument(..., help="Repository name (e.g. 'github.com/charmbracelet/crush')"),
    path: str = typer.Argument(..., help="File path inside the repository"),
    rev: str = typer.Option("HEAD", "--rev", help="Repository revision/branch/commit SHA"),
    endpoint: str = typer.Option("https://sourcegraph.com", "--endpoint", help="Sourcegraph instance URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Sourcegraph API token"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
):
    """Fetch raw file content from a repository directly."""
    try:
        client = _get_client(endpoint, token, timeout)
        content = client.get_file_content(repo, path, rev)
        typer.echo(content, color=False)
    except SourcegraphError as err:
        typer.secho(f"Error: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command(name="tree")
def tree_cmd(
    repo: str = typer.Argument(..., help="Repository name (e.g. 'github.com/charmbracelet/crush')"),
    path: str = typer.Option("", "--path", help="Directory path inside the repository (default is root)"),
    rev: str = typer.Option("HEAD", "--rev", help="Repository revision/branch/commit SHA"),
    endpoint: str = typer.Option("https://sourcegraph.com", "--endpoint", help="Sourcegraph instance URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Sourcegraph API token"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
):
    """List file tree/entries inside a path in the repository."""
    try:
        client = _get_client(endpoint, token, timeout)
        entries = client.get_file_tree(repo, path, rev)
        
        if not entries:
            typer.echo("Directory is empty.")
            return

        for entry in entries:
            name = entry.get("name", "")
            is_dir = entry.get("isDirectory", False)
            if is_dir:
                typer.echo(f"📁 {name}/")
            else:
                typer.echo(f"📄 {name}")
    except SourcegraphError as err:
        typer.secho(f"Error: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

def _format_nodes(nodes: List[Dict[str, Any]]) -> str:
    lines = []
    for node in nodes:
        resource = node.get("resource", {})
        repo_name = resource.get("repository", {}).get("name", "")
        file_path = resource.get("path", "")
        
        rng = node.get("range", {})
        start = rng.get("start", {})
        line_num = int(start.get("line", 0)) + 1  # LSIF line numbers are 0-indexed
        char_num = int(start.get("character", 0)) + 1
        
        url = node.get("url", "")
        lines.append(f"- **{repo_name}/{file_path}#L{line_num}:{char_num}** -> {url}")
    return "\n".join(lines)

@app.command(name="define")
def define_cmd(
    repo: str = typer.Argument(..., help="Repository name"),
    path: str = typer.Argument(..., help="File path inside the repository"),
    line: int = typer.Argument(..., help="Line number (1-indexed)"),
    character: int = typer.Argument(..., help="Character number (1-indexed)"),
    rev: str = typer.Option("HEAD", "--rev", help="Repository revision"),
    endpoint: str = typer.Option("https://sourcegraph.com", "--endpoint", help="Sourcegraph instance URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Sourcegraph API token"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON results"),
):
    """Find definitions for the symbol at the given file position (LSIF/SCIP)."""
    try:
        # Convert to 0-indexed for LSIF/SCIP API
        client = _get_client(endpoint, token, timeout)
        lsif = client.get_code_intel(repo, path, line - 1, character - 1, rev)
        definitions = lsif.get("definitions", {}).get("nodes", [])
        
        if json_output:
            typer.echo(json.dumps(definitions, indent=2))
        else:
            if not definitions:
                typer.echo("No definitions found.")
            else:
                typer.echo("# Definitions\n")
                typer.echo(_format_nodes(definitions))
    except SourcegraphError as err:
        typer.secho(f"Error: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command(name="refs")
def refs_cmd(
    repo: str = typer.Argument(..., help="Repository name"),
    path: str = typer.Argument(..., help="File path inside the repository"),
    line: int = typer.Argument(..., help="Line number (1-indexed)"),
    character: int = typer.Argument(..., help="Character number (1-indexed)"),
    rev: str = typer.Option("HEAD", "--rev", help="Repository revision"),
    endpoint: str = typer.Option("https://sourcegraph.com", "--endpoint", help="Sourcegraph instance URL"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Sourcegraph API token"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON results"),
):
    """Find references for the symbol at the given file position (LSIF/SCIP)."""
    try:
        # Convert to 0-indexed for LSIF/SCIP API
        client = _get_client(endpoint, token, timeout)
        lsif = client.get_code_intel(repo, path, line - 1, character - 1, rev)
        references = lsif.get("references", {}).get("nodes", [])
        
        if json_output:
            typer.echo(json.dumps(references, indent=2))
        else:
            if not references:
                typer.echo("No references found.")
            else:
                typer.echo("# References\n")
                typer.echo(_format_nodes(references))
    except SourcegraphError as err:
        typer.secho(f"Error: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
