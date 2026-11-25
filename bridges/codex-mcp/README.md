# Codex CLI Streamable HTTP MCP Bridge (`codex-mcp`)

Exposes local or sidecar [Codex CLI](https://github.com/openai/codex) execution to kagent `RemoteMCPServer` and Slipway `AgentSet` seats over Streamable HTTP MCP.

Designed for multi-model teams that separate a high-reasoning model (`CODEX_ARCHITECT_MODEL`, e.g., `gpt-6.2-sol`) for architecture, review, and black-box QA from a fast implementation model (`CODEX_BUILDER_MODEL`, e.g., `gpt-6.1-terra`) for scoped parallel implementation.

## Tools Exposed

- `codex_design(repo_url, task, output_schema_json="")` — Read-only architecture and planning on a fresh checkout using `CODEX_ARCHITECT_MODEL`.
- `codex_implement(repo_url, base_commit, candidate_branch, task, writes_csv="")` — Scoped implementation on a fresh worktree checked out at `base_commit`, commits and pushes `candidate_branch` using `CODEX_BUILDER_MODEL`.
- `codex_review(repo_url, base_commit, candidate_branch, candidate_commit, task="")` — Read-only diff and repository review returning `{approved, testedCommit, score, summary}` using `CODEX_ARCHITECT_MODEL`.
- `codex_qa(repo_url, task)` — Black-box and end-to-end evaluation returning `{passed, testedCommit, summary, bugsFound, improvements, metricsSummary}` using `CODEX_ARCHITECT_MODEL`.

## Quick Start (Host Bridge for Local `kind` Clusters)

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

CODEX_BIN=/path/to/codex \
CODEX_ARCHITECT_MODEL=gpt-6.2-sol \
CODEX_BUILDER_MODEL=gpt-6.1-terra \
GIT_REWRITE_FROM=http://git.kagent.svc.cluster.local/ \
GIT_REWRITE_TO=http://127.0.0.1:8096/ \
CODEX_MCP_PORT=8095 \
.venv/bin/python server.py
```

Then edit the host IP in `k8s-remote-mcp.yaml` (for `kind` on macOS/Colima, `host.docker.internal` typically resolves to `192.168.5.2`) and apply:

```sh
kubectl apply -f k8s-remote-mcp.yaml
```
