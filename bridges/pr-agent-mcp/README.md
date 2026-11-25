# PR-Agent Streamable HTTP MCP Bridge (`pr-agent-mcp`)

Containerized Streamable HTTP MCP server wrapping [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) (`PlainDiffGitProvider` + `--json-output`) as a deterministic Slipway review gate.

## Tool Exposed

- `review_candidate(repository, base_commit, candidate_branch, candidate_commit)` — Fetches `candidate_branch`, confirms its tip equals `candidate_commit`, diffs `base_commit..candidate_commit`, runs `pr-agent review --diff-file ... --json-output ...`, and returns `{approved, testedCommit, score, securityConcerns, summary, prAgentReview}` for Slipway's `output.schemaFrom` and CEL `successWhen` gate.

## Build & Deploy

```sh
docker build -t pr-agent-mcp:dev bridges/pr-agent-mcp
# For local kind clusters:
kind load docker-image pr-agent-mcp:dev --name slipway-e2e

# Create your provider key Secret (example for Gemini):
kubectl -n kagent create secret generic gemini-api-key --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY"

# Deploy Deployment, Service, and kagent RemoteMCPServer:
kubectl apply -f bridges/pr-agent-mcp/deployment.yaml
```

Then attach the reviewer overlay from [`teams/software-factory/overlays/pr-agent-reviewer.yaml`](../../teams/software-factory/overlays/pr-agent-reviewer.yaml).
