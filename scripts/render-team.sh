#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: render-team.sh <team-dir> [--overlay <name>] [--apply]

Renders a Slipway team pack by substituting placeholder tokens with environment
variables, printing the resulting multi-document YAML (or applying it via kubectl).

Environment variables (with defaults):
  NAMESPACE        Target Kubernetes namespace (default: kagent)
  TEAM_NAME        Team / AgentSet prefix (default: basename of team-dir)
  MODEL_CONFIG     kagent ModelConfig name (default: default-model)
  HARNESS_REF      kagent Harness name (default: kagent-default)
  REPO_URL         Git repository URL for Git-backed teams (default: http://git.kagent.svc.cluster.local/app.git)
  TARGET_BRANCH    Target Git branch (default: main)
  GIT_SECRET       Secret holding authorization-header (default: app-git-credentials)
  VERIFIER_IMAGE   Digest-pinned verifier image (@sha256:...)
  TARGET_SCOPE     Hierarchical scope for non-Git teams (default: staging/app)
  SERVICE_NAME     Service name for SRE rollout team (default: checkout)
EOF
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

TEAM_DIR="$1"
shift

OVERLAY=""
APPLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --overlay)
      OVERLAY="${2:?--overlay requires a name}"
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$TEAM_DIR" ]]; then
  echo "team directory not found: $TEAM_DIR" >&2
  exit 1
fi

NAMESPACE="${NAMESPACE:-kagent}"
TEAM_NAME="${TEAM_NAME:-$(basename "$TEAM_DIR")}"
MODEL_CONFIG="${MODEL_CONFIG:-default-model}"
HARNESS_REF="${HARNESS_REF:-kagent-default}"
REPO_URL="${REPO_URL:-http://git.kagent.svc.cluster.local/app.git}"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
GIT_SECRET="${GIT_SECRET:-app-git-credentials}"
VERIFIER_IMAGE="${VERIFIER_IMAGE:-registry.example.com/slipway/verifier@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef}"
TARGET_SCOPE="${TARGET_SCOPE:-staging/app}"
SERVICE_NAME="${SERVICE_NAME:-checkout}"

render_file() {
  local file="$1"
  python3 - "$file" <<'PY'
import os, pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
replacements = {
    "__NAMESPACE__": os.environ["NAMESPACE"],
    "__TEAM_NAME__": os.environ["TEAM_NAME"],
    "__MODEL_CONFIG__": os.environ["MODEL_CONFIG"],
    "__HARNESS_REF__": os.environ["HARNESS_REF"],
    "__REPO_URL__": os.environ["REPO_URL"],
    "__TARGET_BRANCH__": os.environ["TARGET_BRANCH"],
    "__GIT_SECRET__": os.environ["GIT_SECRET"],
    "__VERIFIER_IMAGE__": os.environ["VERIFIER_IMAGE"],
    "__TARGET_SCOPE__": os.environ["TARGET_SCOPE"],
    "__SERVICE_NAME__": os.environ["SERVICE_NAME"],
}
for k, v in replacements.items():
    text = text.replace(k, v)
sys.stdout.write(text)
if not text.endswith("\n"):
    sys.stdout.write("\n")
PY
}

export NAMESPACE TEAM_NAME MODEL_CONFIG HARNESS_REF REPO_URL TARGET_BRANCH GIT_SECRET VERIFIER_IMAGE TARGET_SCOPE SERVICE_NAME

FILES=()
for base in schemas.yaml verifier.yaml agents.yaml agentset.yaml recipe.yaml recipes.yaml schedule.yaml; do
  if [[ -f "$TEAM_DIR/$base" ]]; then
    FILES+=("$TEAM_DIR/$base")
  fi
done

if [[ -n "$OVERLAY" ]]; then
  OVERLAY_FILE="$TEAM_DIR/overlays/$OVERLAY.yaml"
  if [[ ! -f "$OVERLAY_FILE" ]]; then
    echo "overlay not found: $OVERLAY_FILE" >&2
    exit 1
  fi
  FILES+=("$OVERLAY_FILE")
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "no manifest files found in $TEAM_DIR" >&2
  exit 1
fi

RENDERED="$(mktemp)"
trap 'rm -f "$RENDERED"' EXIT

for i in "${!FILES[@]}"; do
  if [[ "$i" -gt 0 ]]; then
    echo "---" >> "$RENDERED"
  fi
  render_file "${FILES[$i]}" >> "$RENDERED"
done

if [[ "$APPLY" == "true" ]]; then
  kubectl apply -f "$RENDERED"
else
  cat "$RENDERED"
fi
