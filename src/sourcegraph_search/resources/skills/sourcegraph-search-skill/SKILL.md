---
name: sourcegraph-search-skill
description: Searches code, navigates definitions, references, and code tree hierarchies, and fetches file content across repositories via Sourcegraph's GraphQL API. Use when searching for code symbols, analyzing codebase structures, finding definitions or usages/references of classes/methods, or fetching raw files from Git repositories indexed on Sourcegraph.
dependencies: python>=3.11
allowed-tools:
  - Bash
---

# Sourcegraph Search Skill

`sourcegraph-search` is a CLI tool and client library that enables token-efficient code search and code navigation via Sourcegraph's GraphQL API. It supports standard search, repository directory tree listing, raw file fetching, and LSIF/SCIP code intelligence navigation (definitions and references).

## 📦 Installation

Ensure `sourcegraph-search` is installed. It is recommended to install it globally using `uv`:

1. **Install `uv`** (if not already installed):
   - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

2. **Install `sourcegraph-search`**:
   ```bash
   uv tool install sourcegraph-search
   ```

3. **Install the Skills configurations**:
   ```bash
   # Install the skills (for Codex, Antigravity, Crush, and Claude Code)
   sourcegraph-search skills install
   ```

## 🚀 Quick Start

Run commands directly (if installed via `uv tool install`) or using `uv run` (if executing inside the project directory):

```bash
# Search for occurrences of a class in a repository
sourcegraph-search search "repo:github.com/charmbracelet/crush NewSourcegraphTool"

# Fetch file content directly from a repo
sourcegraph-search fetch "github.com/charmbracelet/crush" "main.go"
```

---

## 🛠️ CLI Reference

### Environment Variables
Configure these variables for seamless usage:
- `SOURCEGRAPH_TOKEN` or `SOURCEGRAPH_API_TOKEN`: Your Sourcegraph personal access token.

### Subcommands

#### 1. Code Search (`search`)
Search for code, symbols, commits, and repositories using Sourcegraph's query syntax.
```bash
sourcegraph-search search "QUERY" [OPTIONS]
```
- `-n, --count INTEGER`: Number of results to return (default: `10`, max: `20`). **Conserve tokens by keeping this low.**
- `-c, --context-window INTEGER`: Number of lines of context to display around each match (default: `10`). Set to `0` if you do not need context content.
- `--endpoint TEXT`: Sourcegraph instance URL (default: `https://sourcegraph.com`).
- `-t, --token TEXT`: Sourcegraph API token (overrides environment variables).
- `--json`: Output raw JSON results instead of formatted markdown.

#### 2. Fetch File (`fetch`)
Fetch raw file content from a repository directly without cloning.
```bash
sourcegraph-search fetch "REPO" "PATH" [OPTIONS]
```
- `--rev TEXT`: Repository revision/branch/commit SHA (default: `HEAD`).
- `--endpoint TEXT`: Sourcegraph instance URL.
- `-t, --token TEXT`: Sourcegraph API token.

#### 3. Directory Tree (`tree`)
List files and subdirectories inside a path within the repository.
```bash
sourcegraph-search tree "REPO" [OPTIONS]
```
- `--path TEXT`: Directory path inside the repository (default: root `""`).
- `--rev TEXT`: Repository revision/branch/commit SHA (default: `HEAD`).

#### 4. Find Definition (`define`)
Find definitions for the symbol at the given file position using LSIF/SCIP code intelligence.
```bash
sourcegraph-search define "REPO" "PATH" LINE CHARACTER [OPTIONS]
```
- `LINE`: Line number (1-indexed).
- `CHARACTER`: Character number (1-indexed).
- `--rev TEXT`: Repository revision (default: `HEAD`).
- `--json`: Output raw JSON results.

#### 5. Find References (`refs`)
Find references/usages for the symbol at the given file position using LSIF/SCIP code intelligence.
```bash
sourcegraph-search refs "REPO" "PATH" LINE CHARACTER [OPTIONS]
```
- `LINE`: Line number (1-indexed).
- `CHARACTER`: Character number (1-indexed).
- `--rev TEXT`: Repository revision (default: `HEAD`).
- `--json`: Output raw JSON results.

---

## 🔍 Search Operators & Syntax

Sourcegraph search queries support powerful filters:
- `repo:github.com/user/project`: Scope search to a specific repository (can use regex, e.g. `repo:^github\.com/user/.*`).
- `file:\.py$`: Match only files with a specific extension/pattern.
- `lang:python`: Filter by programming language.
- `type:symbol`: Find symbol definitions (classes, functions) rather than plain text matches.
- `case:yes`: Enable case-sensitive search.
- `patternType:regexp`: Perform search using regular expressions.

Example query:
```bash
sourcegraph-search search "repo:github.com/charmbracelet/crush lang:Go type:symbol func Main"
```

---

## 🤖 Agent System Guidelines & Rules

When acting as an AI developer or analysis agent, follow these instructions to maximize efficiency and minimize token overhead:

### 📋 Rules of Engagement
1. **Prefer `define` and `refs` over full file fetches**: If you need to understand how a class or method is used or defined, use `define` or `refs` first instead of fetching the entire file using `fetch`. This saves valuable context tokens.
2. **Limit search context and counts**: When searching, default to low count limits (`-n 5` or `-n 10`) and a tight context window (`-c 5` or `-c 0` if you only need paths) to avoid flooding your context window.
3. **Handle missing tokens gracefully**: If `SOURCEGRAPH_TOKEN` is not configured, inform the user clearly that they need to set the environment variable.
4. **Iterative exploration**: 
   - Start by locating the target symbol/file via `search`.
   - List directories via `tree` to inspect package layouts if needed.
   - Use `define` to find where a function/class is implemented.
   - Fetch specific files via `fetch` only when you need to read or edit the code.
