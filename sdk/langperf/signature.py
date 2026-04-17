"""Auto-detect agent identity at SDK init() time.

Signature rules:
  1. If running inside a git working tree AND `origin` is configured:
        signature = "git:" + origin_url + ":" + init_caller_path_relative_to_repo_root
     git_sha / short_sha / git_origin accompany the signature as separate attrs.
  2. Otherwise:
        signature = "mod:" + hostname + ":" + init_caller_module

Version rules:
  - git_sha / short_sha: from `git rev-parse HEAD`, if available
  - package_version: from importlib.metadata.version(<top_level_package>) where
    <top_level_package> is the first segment of the init caller's __name__.

All functions fail soft — they return None rather than raising — so a missing
git binary or a broken package metadata install doesn't block tracing.
"""

from __future__ import annotations

import inspect
import logging
import socket
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Optional

logger = logging.getLogger("langperf.signature")


@dataclass(frozen=True)
class AgentIdentity:
    signature: str
    git_origin: Optional[str]
    git_sha: Optional[str]
    short_sha: Optional[str]
    package_version: Optional[str]
    language: str = "python"


def detect(caller_stack_offset: int = 2) -> AgentIdentity:
    """Return the best-effort agent identity for the current process.

    `caller_stack_offset` is how many frames above detect() the actual caller
    of langperf.init() lives. The default (2) is correct when detect() is
    called directly from init(). If you call detect() via a wrapper, bump.
    """
    caller_path, caller_module = _caller_info(caller_stack_offset)
    repo_root, origin = _git_context_for(caller_path)

    if repo_root and origin:
        try:
            rel = str(caller_path.resolve().relative_to(repo_root))
        except ValueError:
            # Caller is outside the detected repo (rare — e.g. installed package
            # inside a git checkout). Fall back to module-based signature.
            rel = None
        if rel is not None:
            signature = f"git:{origin}:{rel}"
        else:
            signature = f"mod:{socket.gethostname()}:{caller_module}"
    else:
        signature = f"mod:{socket.gethostname()}:{caller_module}"

    git_sha, short_sha = _git_head(repo_root) if repo_root else (None, None)
    pkg = _package_version_for(caller_module)

    return AgentIdentity(
        signature=signature,
        git_origin=origin,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=pkg,
    )


def _caller_info(stack_offset: int) -> tuple[Path, str]:
    frame = inspect.stack()[stack_offset]
    module_name = frame.frame.f_globals.get("__name__", "__unknown__")
    file_path = Path(frame.filename)
    return file_path, module_name


def _git_context_for(path: Path) -> tuple[Optional[Path], Optional[str]]:
    """Return (repo_root, origin_url) or (None, None)."""
    try:
        root = _git(path.parent, "rev-parse", "--show-toplevel")
    except _GitError:
        return None, None
    root_path = Path(root.strip())
    try:
        origin = _git(root_path, "remote", "get-url", "origin")
    except _GitError:
        return root_path, None
    return root_path, origin.strip()


def _git_head(root: Path) -> tuple[Optional[str], Optional[str]]:
    try:
        sha = _git(root, "rev-parse", "HEAD").strip()
    except _GitError:
        return None, None
    return sha, (sha[:7] if sha else None)


class _GitError(RuntimeError):
    pass


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise _GitError(str(exc)) from exc
    if result.returncode != 0:
        raise _GitError(result.stderr.strip() or "git exited non-zero")
    return result.stdout


def _package_version_for(module_name: str) -> Optional[str]:
    if not module_name or module_name.startswith("__"):
        return None
    top = module_name.split(".", 1)[0]
    if not top:
        return None
    try:
        return pkg_version(top)
    except PackageNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 — be generous; metadata layouts vary
        logger.debug("pkg_version(%s) failed: %s", top, exc)
        return None
