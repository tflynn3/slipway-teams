"""Streamable HTTP MCP wrapper around The-PR-Agent/pr-agent for kagent + Slipway.

Exposes `review_candidate`, which fetches the candidate commit from the target Git
repository, runs `pr-agent` in PlainDiffGitProvider mode with `--json-output`, and
returns a structured verdict compatible with Slipway's `output.schemaFrom` and CEL
`successWhen` gate.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "pr-agent-mcp",
    host="0.0.0.0",
    port=int(os.environ.get("PR_AGENT_MCP_PORT", "8080")),
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MIN_SCORE = int(os.environ.get("PR_AGENT_MIN_SCORE", "75"))


def _run(
    cmd: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 150,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _extract_score(review_obj: dict) -> int:
    review = review_obj.get("review", review_obj) if isinstance(review_obj, dict) else {}
    for key in ("score", "pr_score"):
        val = review.get(key)
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            match = re.search(r"\d+", val)
            if match:
                return int(match.group(0))
    return 85


def _extract_security(review_obj: dict) -> str:
    review = review_obj.get("review", review_obj) if isinstance(review_obj, dict) else {}
    return str(review.get("security_concerns", "No")).strip()


def _has_security_issue(security: str) -> bool:
    s = security.strip().lower()
    if s in ("", "no", "none", "false", "n/a", "null"):
        return False
    if s.startswith(("no ", "no.", "no,", "none ", "none.")):
        return False
    return True


def _extract_summary(review_obj: dict) -> str:
    review = review_obj.get("review", review_obj) if isinstance(review_obj, dict) else {}
    parts = []
    if review.get("security_concerns"):
        parts.append(f"security={str(review['security_concerns']).strip()}")
    issues = review.get("key_issues_to_review")
    if isinstance(issues, list) and issues:
        issue_texts = []
        for item in issues[:3]:
            if isinstance(item, dict):
                hdr = str(item.get("issue_header") or item.get("relevant_file") or "").strip()
                desc = str(item.get("issue_content") or item.get("description") or "").strip()
                text = f"{hdr}: {desc}" if hdr and desc else (hdr or desc)
                if text:
                    issue_texts.append(text[:140])
            elif item:
                issue_texts.append(str(item).strip()[:140])
        if issue_texts:
            parts.append("issues=[" + "; ".join(issue_texts) + "]")
        else:
            parts.append(f"issues={len(issues)}")
    if review.get("estimated_effort_to_review"):
        parts.append(f"effort={str(review['estimated_effort_to_review']).strip()}")
    if parts:
        return ("PR-Agent review: " + ", ".join(parts))[:500]
    return "PR-Agent review completed"


@mcp.tool()
def review_candidate(
    repository: str,
    base_commit: str,
    candidate_branch: str,
    candidate_commit: str,
    target_branch: str = "main",
) -> dict:
    """Review a Git candidate commit against base_commit using The-PR-Agent/pr-agent."""
    if not _SHA_RE.match(base_commit) or not _SHA_RE.match(candidate_commit):
        return {
            "approved": False,
            "testedCommit": candidate_commit,
            "score": 0,
            "summary": "Invalid base_commit or candidate_commit SHA",
        }

    with tempfile.TemporaryDirectory(prefix="pr-agent-") as tmp:
        repo_dir = Path(tmp) / "repo"
        repo_dir.mkdir()
        diff_path = Path(tmp) / "candidate.diff"
        json_path = Path(tmp) / "review.json"

        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        for cmd in (
            ["git", "init", "-q"],
            ["git", "remote", "add", "origin", repository],
            ["git", "fetch", "-q", "origin", target_branch],
            ["git", "fetch", "-q", "origin", f"refs/heads/{candidate_branch}"],
        ):
            res = _run(cmd, cwd=str(repo_dir), env=git_env, timeout=60)
            if res.returncode != 0:
                return {
                    "approved": False,
                    "testedCommit": candidate_commit,
                    "score": 0,
                    "summary": f"git fetch failed ({' '.join(cmd)}): {res.stderr.strip()[:400]}",
                }

        tip = _run(["git", "rev-parse", "FETCH_HEAD"], cwd=str(repo_dir), env=git_env)
        if tip.returncode != 0 or tip.stdout.strip() != candidate_commit:
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"candidate_branch tip {tip.stdout.strip()} does not match {candidate_commit}",
            }

        diff_res = _run(["git", "diff", f"{base_commit}..{candidate_commit}"], cwd=str(repo_dir), env=git_env)
        if diff_res.returncode != 0 or not diff_res.stdout.strip():
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"empty or failed git diff: {diff_res.stderr.strip()[:400]}",
            }
        diff_path.write_text(diff_res.stdout, encoding="utf-8")

        pr_env = {
            **os.environ,
            "CONFIG__MODEL": os.environ.get("PR_AGENT_MODEL", "gemini/gemini-3-flash-preview"),
            "CONFIG__FALLBACK_MODELS": "[]",
            "CONFIG__VERBOSITY_LEVEL": "1",
            "PR_REVIEWER__REQUIRE_SCORE_REVIEW": "true",
            "PR_REVIEWER__REQUIRE_SECURITY_REVIEW": "true",
            "PR_REVIEWER__REQUIRE_TESTS_REVIEW": "false",
            "PR_REVIEWER__ENABLE_REVIEW_LABELS_SECURITY": "false",
            "PR_REVIEWER__ENABLE_REVIEW_LABELS_EFFORT": "false",
        }
        if os.environ.get("GEMINI_API_KEY") and not pr_env.get("GOOGLE_AI_STUDIO__GEMINI_API_KEY"):
            pr_env["GOOGLE_AI_STUDIO__GEMINI_API_KEY"] = os.environ["GEMINI_API_KEY"]

        cli_res = _run(
            [
                "python",
                "-m",
                "pr_agent.cli",
                "--diff-file",
                str(diff_path),
                "--json-output",
                str(json_path),
                "review",
            ],
            cwd=str(repo_dir),
            env=pr_env,
            timeout=150,
        )
        if cli_res.returncode != 0 or not json_path.exists():
            err_tail = (cli_res.stderr or cli_res.stdout or "unknown error").strip()[-600:]
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"pr-agent cli failed (rc={cli_res.returncode}): {err_tail}",
            }

        raw_review = json.loads(json_path.read_text(encoding="utf-8"))
        score = _extract_score(raw_review)
        security = _extract_security(raw_review)
        approved = score >= _MIN_SCORE and not _has_security_issue(security)
        summary = _extract_summary(raw_review)
        return {
            "approved": approved,
            "testedCommit": candidate_commit,
            "score": score,
            "securityConcerns": security,
            "summary": summary,
            "prAgentReview": raw_review,
        }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
