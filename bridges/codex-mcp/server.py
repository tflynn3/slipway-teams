"""Streamable HTTP MCP bridge exposing Codex CLI multi-model tools to kagent + Slipway.

Separates a high-reasoning architect/reviewer/QA model (`CODEX_ARCHITECT_MODEL`) from
an implementation model (`CODEX_BUILDER_MODEL`). Runs each invocation in a fresh,
isolated temporary Git worktree with `--ignore-user-config --ephemeral`.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
ARCHITECT_MODEL = os.environ.get("CODEX_ARCHITECT_MODEL", "gpt-6.2-sol")
BUILDER_MODEL = os.environ.get("CODEX_BUILDER_MODEL", "gpt-6.1-terra")
ARCHITECT_EFFORT = os.environ.get("CODEX_ARCHITECT_EFFORT", "high")
BUILDER_EFFORT = os.environ.get("CODEX_BUILDER_EFFORT", "medium")
GIT_REWRITE_FROM = os.environ.get("GIT_REWRITE_FROM", "")
GIT_REWRITE_TO = os.environ.get("GIT_REWRITE_TO", "")
GIT_AUTHOR_NAME = os.environ.get("GIT_AUTHOR_NAME", "slipway-builder")
GIT_AUTHOR_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "builder@slipway.local")
STATE_DIR = Path(os.environ.get("CODEX_STATE_DIR", "./state"))
STATE_DIR.mkdir(parents=True, exist_ok=True)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

mcp = FastMCP(
    "codex-mcp",
    host="0.0.0.0",
    port=int(os.environ.get("CODEX_MCP_PORT", "8095")),
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _rewrite_repo_url(url: str) -> str:
    if GIT_REWRITE_FROM and GIT_REWRITE_TO:
        return url.replace(GIT_REWRITE_FROM, GIT_REWRITE_TO)
    return url


def _run(
    cmd: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 480,
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


def _extract_json_object(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def _run_codex(
    model: str,
    effort: str,
    cwd: str,
    prompt: str,
    sandbox: str = "read-only",
    full_access: bool = False,
    output_schema: dict | None = None,
    timeout: int = 480,
) -> tuple[int, str, str, float]:
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="codex-io-") as io_dir:
        out_file = Path(io_dir) / "last_message.txt"
        cmd = [
            CODEX_BIN,
            "exec",
            "--ignore-user-config",
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            "--skip-git-repo-check",
            "--ephemeral",
            "-C",
            cwd,
            "-o",
            str(out_file),
        ]
        if full_access:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            cmd.extend(["-s", sandbox])
        if output_schema is not None:
            schema_file = Path(io_dir) / "schema.json"
            schema_file.write_text(json.dumps(output_schema), encoding="utf-8")
            cmd.extend(["--output-schema", str(schema_file)])
        cmd.append(prompt)

        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        res = _run(cmd, cwd=cwd, env=env, timeout=timeout)
        elapsed = time.time() - t0
        last_msg = out_file.read_text(encoding="utf-8").strip() if out_file.exists() else ""
        if not last_msg:
            last_msg = (res.stdout or "").strip()
        err_tail = (res.stderr or "").strip()[-800:]
        print(
            f"[codex-mcp] model={model} effort={effort} rc={res.returncode} "
            f"elapsed={elapsed:.1f}s out_len={len(last_msg)}",
            flush=True,
        )
        return res.returncode, last_msg, err_tail, elapsed


def _git_clone(repo_url: str, dest: Path, branch: str = "main") -> str | None:
    local_url = _rewrite_repo_url(repo_url)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    res = _run(["git", "clone", "-q", "-b", branch, local_url, str(dest)], env=env, timeout=60)
    if res.returncode != 0:
        return f"git clone failed: {res.stderr.strip()[:400]}"
    return None


@mcp.tool()
def codex_design(
    repo_url: str,
    task: str,
    output_schema_json: str = "",
    branch: str = "main",
) -> dict:
    """Run the architect model for design, feature selection, and work-item planning."""
    schema = None
    if output_schema_json.strip():
        try:
            schema = json.loads(output_schema_json)
        except Exception as exc:
            return {"error": f"invalid output_schema_json: {exc}"}

    with tempfile.TemporaryDirectory(prefix="codex-design-") as tmp:
        repo_dir = Path(tmp) / "repo"
        err = _git_clone(repo_url, repo_dir, branch=branch)
        if err:
            return {"error": err}

        qa_file = STATE_DIR / "latest-qa.json"
        if qa_file.exists():
            shutil.copy2(qa_file, Path(tmp) / "latest-qa.json")
            task = task + "\n\nNote: The latest black-box QA report is available at ../latest-qa.json.\n"

        rc, last_msg, err_tail, elapsed = _run_codex(
            model=ARCHITECT_MODEL,
            effort=ARCHITECT_EFFORT,
            cwd=str(repo_dir),
            prompt=task,
            sandbox="read-only",
            output_schema=schema,
            timeout=540,
        )
        if rc != 0:
            return {"error": f"codex_design failed (rc={rc}): {err_tail or last_msg[:400]}"}
        parsed = _extract_json_object(last_msg)
        if parsed is not None:
            return parsed
        return {"text": last_msg, "elapsedSec": round(elapsed, 1)}


@mcp.tool()
def codex_implement(
    repo_url: str,
    base_commit: str,
    candidate_branch: str,
    task: str,
    writes_csv: str = "",
    branch: str = "main",
) -> dict:
    """Run the builder model to implement a scoped change, test, commit, and push candidate_branch."""
    if not _SHA_RE.match(base_commit):
        return {"error": f"invalid base_commit: {base_commit}"}

    with tempfile.TemporaryDirectory(prefix="codex-build-") as tmp:
        repo_dir = Path(tmp) / "repo"
        err = _git_clone(repo_url, repo_dir, branch=branch)
        if err:
            return {"error": err}

        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": GIT_AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": GIT_AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": GIT_AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": GIT_AUTHOR_EMAIL,
        }
        res = _run(["git", "checkout", "-q", "-b", candidate_branch, base_commit], cwd=str(repo_dir), env=env)
        if res.returncode != 0:
            return {"error": f"git checkout base_commit failed: {res.stderr.strip()[:400]}"}

        prompt = (
            f"You are implementing a scoped change on branch `{candidate_branch}` from base commit `{base_commit}`.\n"
            f"Allowed write paths: {writes_csv or '(as specified in task)'}\n"
            "Rules:\n"
            "- Edit ONLY files inside the allowed write paths.\n"
            "- Run unit/build checks locally to confirm everything compiles and passes.\n"
            "- Do NOT push to git yourself (the bridge commits and pushes candidate_branch).\n"
            "- End with a concise 1-2 sentence summary.\n\n"
            f"Task:\n{task}\n"
        )
        rc, last_msg, err_tail, elapsed = _run_codex(
            model=BUILDER_MODEL,
            effort=BUILDER_EFFORT,
            cwd=str(repo_dir),
            prompt=prompt,
            full_access=True,
            timeout=540,
        )
        if rc != 0:
            return {"error": f"codex_implement failed (rc={rc}): {err_tail or last_msg[:500]}"}

        _run(["git", "add", "-A"], cwd=str(repo_dir), env=env)
        status = _run(["git", "status", "--porcelain"], cwd=str(repo_dir), env=env)
        if status.stdout.strip():
            commit_res = _run(["git", "commit", "-m", f"Implement {candidate_branch}"], cwd=str(repo_dir), env=env)
            if commit_res.returncode != 0:
                return {"error": f"git commit failed: {commit_res.stderr.strip()[:400]}"}

        head = _run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), env=env).stdout.strip()
        if head == base_commit:
            return {"error": "no changes were committed"}

        changed = _run(
            ["git", "diff", "--name-only", f"{base_commit}..{head}"],
            cwd=str(repo_dir),
            env=env,
        ).stdout.strip().splitlines()

        push = _run(
            ["git", "push", "-q", "origin", f"HEAD:refs/heads/{candidate_branch}"],
            cwd=str(repo_dir),
            env=env,
            timeout=60,
        )
        if push.returncode != 0:
            return {"error": f"git push {candidate_branch} failed: {push.stderr.strip()[:400]}"}

        return {
            "candidateBranch": candidate_branch,
            "commit": head,
            "changedFiles": changed,
            "summary": last_msg[:400] or f"Committed {len(changed)} file(s) on {candidate_branch}",
            "elapsedSec": round(elapsed, 1),
        }


@mcp.tool()
def codex_review(
    repo_url: str,
    base_commit: str,
    candidate_branch: str,
    candidate_commit: str,
    task: str = "",
    branch: str = "main",
) -> dict:
    """Run the architect model for strict code, architecture, concurrency, and security review."""
    if not _SHA_RE.match(base_commit) or not _SHA_RE.match(candidate_commit):
        return {
            "approved": False,
            "testedCommit": candidate_commit,
            "score": 0,
            "summary": "Invalid base_commit or candidate_commit SHA",
        }

    with tempfile.TemporaryDirectory(prefix="codex-review-") as tmp:
        repo_dir = Path(tmp) / "repo"
        err = _git_clone(repo_url, repo_dir, branch=branch)
        if err:
            return {"approved": False, "testedCommit": candidate_commit, "score": 0, "summary": err}

        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        fetch = _run(["git", "fetch", "-q", "origin", f"refs/heads/{candidate_branch}"], cwd=str(repo_dir), env=env)
        if fetch.returncode != 0:
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"git fetch candidate failed: {fetch.stderr.strip()[:300]}",
            }
        tip = _run(["git", "rev-parse", "FETCH_HEAD"], cwd=str(repo_dir), env=env).stdout.strip()
        if tip != candidate_commit:
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"branch tip {tip} does not match {candidate_commit}",
            }
        _run(["git", "checkout", "-q", candidate_commit], cwd=str(repo_dir), env=env)
        diff_txt = _run(["git", "diff", f"{base_commit}..{candidate_commit}"], cwd=str(repo_dir), env=env).stdout
        (Path(tmp) / "candidate.diff").write_text(diff_txt, encoding="utf-8")

        review_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "approved": {"type": "boolean"},
                "testedCommit": {"type": "string"},
                "score": {"type": "integer"},
                "summary": {"type": "string"},
            },
            "required": ["approved", "testedCommit", "score", "summary"],
        }
        prompt = (
            f"Inspect commit `{candidate_commit}` and unified diff `../candidate.diff` "
            f"(`{base_commit}..{candidate_commit}`).\n"
            "Evaluate strictly for correctness, concurrency, durability, error handling, and security.\n"
            "Approve (`approved: true`, `score >= 75`) only if there are zero correctness or security defects.\n"
            "If rejecting, cite exact files and fixes needed in `summary`.\n"
            f"Set `testedCommit` to `{candidate_commit}`.\n"
            f"{task}\n"
        )
        rc, last_msg, err_tail, _ = _run_codex(
            model=ARCHITECT_MODEL,
            effort=ARCHITECT_EFFORT,
            cwd=str(repo_dir),
            prompt=prompt,
            sandbox="read-only",
            output_schema=review_schema,
            timeout=480,
        )
        if rc != 0:
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"codex_review failed (rc={rc}): {err_tail or last_msg[:300]}",
            }
        parsed = _extract_json_object(last_msg)
        if not parsed:
            return {
                "approved": False,
                "testedCommit": candidate_commit,
                "score": 0,
                "summary": f"non-JSON review output: {last_msg[:300]}",
            }
        parsed["testedCommit"] = candidate_commit
        return parsed


@mcp.tool()
def codex_qa(repo_url: str, task: str, branch: str = "main") -> dict:
    """Run the architect model for black-box, stress, crash-recovery, and E2E evaluation."""
    with tempfile.TemporaryDirectory(prefix="codex-qa-") as tmp:
        repo_dir = Path(tmp) / "repo"
        err = _git_clone(repo_url, repo_dir, branch=branch)
        if err:
            return {"error": err}

        head = _run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir)).stdout.strip()
        eval_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "passed": {"type": "boolean"},
                "testedCommit": {"type": "string"},
                "summary": {"type": "string"},
                "bugsFound": {"type": "array", "items": {"type": "string"}},
                "improvements": {"type": "array", "items": {"type": "string"}},
                "metricsSummary": {"type": "string"},
            },
            "required": ["passed", "testedCommit", "summary", "bugsFound", "improvements", "metricsSummary"],
        }
        prompt = (
            f"Run rigorous black-box, real-world, crash-recovery, and concurrency testing at commit `{head}`.\n"
            "Never mock away failures. Report concrete bugs, benchmarks, and prioritized improvements.\n"
            f"Set `testedCommit` to `{head}`.\n\nTask:\n{task}\n"
        )
        rc, last_msg, err_tail, _ = _run_codex(
            model=ARCHITECT_MODEL,
            effort=ARCHITECT_EFFORT,
            cwd=str(repo_dir),
            prompt=prompt,
            full_access=True,
            output_schema=eval_schema,
            timeout=540,
        )
        if rc != 0:
            return {
                "passed": False,
                "testedCommit": head,
                "summary": f"codex_qa failed (rc={rc}): {err_tail or last_msg[:300]}",
                "bugsFound": [],
                "improvements": [],
                "metricsSummary": "",
            }
        parsed = _extract_json_object(last_msg) or {
            "passed": False,
            "testedCommit": head,
            "summary": last_msg[:400],
            "bugsFound": [],
            "improvements": [],
            "metricsSummary": "",
        }
        parsed["testedCommit"] = head
        (STATE_DIR / "latest-qa.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        return parsed


if __name__ == "__main__":
    print(
        f"[codex-mcp] listening on 0.0.0.0:{os.environ.get('CODEX_MCP_PORT', '8095')} "
        f"(architect={ARCHITECT_MODEL}, builder={BUILDER_MODEL}, bin={CODEX_BIN})",
        flush=True,
    )
    mcp.run(transport="streamable-http")
