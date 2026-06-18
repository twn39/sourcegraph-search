# sourcegraph-search

A CLI utility in Python to search code and navigate definitions/references across public repositories via Sourcegraph's GraphQL API. This project is inspired by the Sourcegraph tool implementation in Charmbracelet's `crush`.

## Features
- **Advanced Search**: Query code, symbols (`type:symbol`), commits (`type:commit`), and repositories (`type:repo`) using Sourcegraph's syntax.
- **Direct File Operations**: Directly read file content (`fetch`) or browse directory structure (`tree`) without performing a search first.
- **Precise Code Navigation**: Lookup exact definitions (`define`) and usages (`refs`) for a symbol at a specific coordinate using LSIF/SCIP index data.
- **Context Windows**: Display search matching results with lines of context surrounding the matches.
- **JSON Output**: Export raw JSON response payloads for seamless integration with downstream scripts.
- **Custom Instance & Token Support**: Works out of the box with public Sourcegraph or self-hosted enterprise instances.

## Installation

Ensure you have [uv](https://github.com/astral-sh/uv) installed, then run:

```bash
# Clone the repository
git clone https://github.com/your-username/sourcegraph-search.git
cd sourcegraph-search

# Sync/install dependencies and register CLI globally in editable mode
uv sync
```

---

## Command Reference

The CLI uses a subcommand-based interface:
```bash
uv run sourcegraph-search [COMMAND] [ARGS] [OPTIONS]
```

### 1. `search` Subcommand
Search code, symbols, commits, and repositories.

```bash
uv run sourcegraph-search search [OPTIONS] QUERY
```

**Options**:
- `-n, --count INTEGER`: Number of results to return (default: 10, max: 20).
- `-c, --context-window INTEGER`: Number of lines of context to display around matches (default: 10).
- `--endpoint TEXT`: Sourcegraph instance URL (default: `https://sourcegraph.com`).
- `-t, --token TEXT`: Sourcegraph API token.
- `--json`: Output raw JSON results instead of formatted Markdown.
- `--timeout INTEGER`: Request timeout in seconds (default: 30).

**Examples**:
```bash
# General search with context lines
uv run sourcegraph-search search "repo:github.com/charmbracelet/crush NewSourcegraphTool"

# Symbol search
uv run sourcegraph-search search "repo:github.com/charmbracelet/crush type:symbol NewSourcegraphTool"

# Commit search
uv run sourcegraph-search search "repo:github.com/charmbracelet/crush type:commit NewSourcegraphTool"
```

### 2. `fetch` Subcommand
Fetch raw file content from a repository directly.

```bash
uv run sourcegraph-search fetch [OPTIONS] REPO PATH
```

**Options**:
- `--rev TEXT`: Revision/branch/commit SHA (default: `HEAD`).
- `--endpoint TEXT`: Sourcegraph instance URL.
- `-t, --token TEXT`: Sourcegraph API token.

**Example**:
```bash
uv run sourcegraph-search fetch github.com/charmbracelet/crush README.md --rev main
```

### 3. `tree` Subcommand
List file tree/entries inside a path in the repository.

```bash
uv run sourcegraph-search tree [OPTIONS] REPO
```

**Options**:
- `--path TEXT`: Directory path inside the repository (default is repository root).
- `--rev TEXT`: Revision/branch/commit SHA (default: `HEAD`).
- `--endpoint TEXT`: Sourcegraph instance URL.
- `-t, --token TEXT`: Sourcegraph API token.

**Example**:
```bash
uv run sourcegraph-search tree github.com/charmbracelet/crush --path internal/agent/tools
```

### 4. `define` Subcommand
Find definitions for the symbol at the given file position using LSIF/SCIP code intelligence.

```bash
uv run sourcegraph-search define [OPTIONS] REPO PATH LINE CHARACTER
```

**Options**:
- `--rev TEXT`: Repository revision (default: `HEAD`).
- `--endpoint TEXT`: Sourcegraph instance URL.
- `-t, --token TEXT`: Sourcegraph API token.
- `--json`: Output raw JSON results instead of formatted Markdown.

*Note: Line and Character numbers are 1-indexed.*

**Example**:
```bash
uv run sourcegraph-search define github.com/charmbracelet/crush internal/agent/tools/sourcegraph.go 50 10
```

### 5. `refs` Subcommand
Find references/usages for the symbol at the given file position.

```bash
uv run sourcegraph-search refs [OPTIONS] REPO PATH LINE CHARACTER
```

**Options**:
- `--rev TEXT`: Repository revision (default: `HEAD`).
- `--endpoint TEXT`: Sourcegraph instance URL.
- `-t, --token TEXT`: Sourcegraph API token.
- `--json`: Output raw JSON results instead of formatted Markdown.

*Note: Line and Character numbers are 1-indexed.*

**Example**:
```bash
uv run sourcegraph-search refs github.com/charmbracelet/crush internal/agent/tools/sourcegraph.go 50 10
```

---

## Authentication

By default, Sourcegraph allows querying public repositories without authentication. If you run into rate limits or wish to query private instances/repos, supply your API token.

The CLI reads the token in the following order of precedence:
1. The `--token` / `-t` CLI option.
2. The `SOURCEGRAPH_TOKEN` environment variable.
3. The `SOURCEGRAPH_API_TOKEN` environment variable.

Example with inline environment variable:
```bash
SOURCEGRAPH_TOKEN="your_api_token" uv run sourcegraph-search search "repo:github.com/charmbracelet/crush NewSourcegraphTool"
```
