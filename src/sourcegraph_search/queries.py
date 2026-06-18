# Lightweight Search Query (Blazing fast, removes 'content' field to prevent memory & network bloat)
GRAPHQL_SEARCH_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V2, patternType: keyword ) {
    results {
      matchCount
      limitHit
      resultCount
      approximateResultCount
      missing { name }
      timedout { name }
      indexUnavailable
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path, url }
          lineMatches {
            preview
            lineNumber
            offsetAndLengths
          }
          symbols {
            name
            kind
            containerName
            url
          }
        }
        ... on CommitSearchResult {
          commit {
            oid
            message
            author {
              person {
                name
              }
              date
            }
            repository {
              name
            }
          }
          url
        }
        ... on Repository {
          name
          url
        }
      }
    }
  }
}
"""

# Context Preloading Query (Fetches 'content' only when full context window surrounding lines is requested)
GRAPHQL_SEARCH_WITH_CONTENT_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V2, patternType: keyword ) {
    results {
      matchCount
      limitHit
      resultCount
      approximateResultCount
      missing { name }
      timedout { name }
      indexUnavailable
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path, url, content }
          lineMatches {
            preview
            lineNumber
            offsetAndLengths
          }
          symbols {
            name
            kind
            containerName
            url
          }
        }
        ... on CommitSearchResult {
          commit {
            oid
            message
            author {
              person {
                name
              }
              date
            }
            repository {
              name
            }
          }
          url
        }
        ... on Repository {
          name
          url
        }
      }
    }
  }
}
"""

GRAPHQL_FILE_CONTENT_QUERY = """
query GetFileContent($repo: String!, $rev: String!, $path: String!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      file(path: $path) {
        content
      }
    }
  }
}
"""

GRAPHQL_FILE_TREE_QUERY = """
query GetFileTree($repo: String!, $rev: String!, $path: String!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      tree(path: $path) {
        entries {
          name
          path
          isDirectory
          url
        }
      }
    }
  }
}
"""

GRAPHQL_CODE_INTEL_QUERY = """
query CodeIntel($repo: String!, $rev: String!, $path: String!, $line: Int!, $character: Int!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      blob(path: $path) {
        lsif {
          definitions(line: $line, character: $character) {
            nodes {
              resource {
                path
                repository {
                  name
                }
              }
              range {
                start {
                  line
                  character
                }
                end {
                  line
                  character
                }
              }
              url
            }
          }
          references(line: $line, character: $character) {
            nodes {
              resource {
                path
                repository {
                  name
                }
              }
              range {
                start {
                  line
                  character
                }
                end {
                  line
                  character
                }
              }
              url
            }
          }
        }
      }
    }
  }
}
"""
