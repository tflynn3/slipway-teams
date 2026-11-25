# Software Factory Team Pack

Autonomous software development team separating high-reasoning architecture/review/QA from parallel scoped implementation, backed by Slipway's trusted verifier Jobs, `PathLease` conflict coordination, and continuous black-box evaluation.

## Seats (`AgentSet`)

| Seat | Replicas | `resetPolicy` | Role |
|---|---|---|---|
| `architect` | 1 | `Never` | Retains long-horizon architecture and design context across cycles |
| `builder` | 2 | `OnFailure` | Implements scoped backlog items in parallel under `PathLease` |
| `reviewer` | 1 | `AfterAssignment` | Fresh code, concurrency, and security review per candidate commit |
| `qa` | 1 | `AfterAssignment` | Fresh black-box evaluation and bug hunting per cycle |

## Overlays

- **`codex-dual-model`** — Pairs Codex `gpt-6.2-sol` (`architect`, `reviewer`, `qa`) with Codex `gpt-6.1-terra` (`builder` ×2) via [`bridges/codex-mcp`](../../bridges/codex-mcp).
- **`pr-agent-reviewer`** — Swaps the `reviewer` seat to [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) via [`bridges/pr-agent-mcp`](../../bridges/pr-agent-mcp).

## Usage

```sh
# 1. Start your MCP bridge (e.g., bridges/codex-mcp or bridges/pr-agent-mcp)
# 2. Apply the team pack with your repository, credentials Secret, and digest-pinned verifier:
NAMESPACE=kagent \
TEAM_NAME=myapp \
MODEL_CONFIG=my-model \
REPO_URL=http://git.kagent.svc.cluster.local/myapp.git \
GIT_SECRET=myapp-git-credentials \
VERIFIER_IMAGE=ghcr.io/example/myapp-verifier@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/software-factory --overlay codex-dual-model --apply
```
