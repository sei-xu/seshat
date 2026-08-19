"""Git synchronization protocol for vault changes.

Handles pulling changes from the vault, committing new items, and detecting
conflicts. Per the design principle: refuse and warn on conflicts rather than
attempting automatic resolution.

Implements protocol from seixu/seshat/11_git_conflitos.md.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class GitSyncError(ValueError):
    """Error during git sync operations — vault state conflict or git failure."""


class ConflictDetectedError(GitSyncError):
    """Merge conflict detected — Seshat refuses to auto-resolve."""


@dataclass
class SyncStatus:
    """Result of a sync operation."""

    status: Literal["clean", "conflicts", "error"]
    message: str
    conflicted_files: list[str]


class GitVault:
    """Manages git operations on a vault clone."""

    def __init__(self, vault_root: str | Path):
        self.vault_root = Path(vault_root).resolve()
        if not self.vault_root.is_dir():
            raise GitSyncError(f"vault root not found: {self.vault_root}")
        self.git_dir = self.vault_root / ".git"

    def is_initialized(self) -> bool:
        """Check if vault has git repo initialized."""
        return self.git_dir.is_dir()

    def init(self) -> None:
        """Initialize git repository in vault root."""
        if self.is_initialized():
            return
        try:
            subprocess.run(
                ["git", "init"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"git init failed: {e.stderr.decode()}") from e

    def add_remote(self, name: str, url: str) -> None:
        """Add remote repository (usually 'origin')."""
        if not self.is_initialized():
            self.init()
        try:
            subprocess.run(
                ["git", "remote", "add", name, url],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode()
            if "already exists" in stderr:
                return  # remote already exists, ignore
            raise GitSyncError(f"git remote add failed: {stderr}") from e

    def has_changes(self) -> bool:
        """Check if working tree has uncommitted changes."""
        if not self.is_initialized():
            return False
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"git status check failed: {e.stderr.decode()}") from e

    def commit(
        self,
        message: str,
        author_name: str = "Seshat",
        author_email: str = "seshat@seîxu.local",
    ) -> str:
        """Commit current changes. Returns commit hash on success."""
        if not self.has_changes():
            raise GitSyncError("no changes to commit")

        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    message,
                    f"--author={author_name} <{author_email}>",
                ],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            # Get the commit hash using git rev-parse
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"git commit failed: {e.stderr.decode()}") from e

    def pull(self, remote: str = "origin", branch: str = "main") -> SyncStatus:
        """
        Pull changes from remote. Detects conflicts but refuses to auto-resolve.

        Returns SyncStatus with:
        - status: "clean" (no changes), "conflicts" (detected), "error" (git failure)
        - message: Human-readable status message
        - conflicted_files: List of files with merge conflicts
        """
        if not self.is_initialized():
            raise GitSyncError("git repository not initialized")

        try:
            # Use --no-rebase (merge strategy) to ensure merge commit on conflicts
            result = subprocess.run(
                ["git", "pull", "--no-rebase", remote, branch],
                cwd=self.vault_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Clean merge
                return SyncStatus(
                    status="clean",
                    message=f"Successfully pulled {remote}/{branch}",
                    conflicted_files=[],
                )

            # Check if pull failed due to conflicts
            if "conflict" in result.stderr.lower() or "conflict" in result.stdout.lower():
                # List conflicted files BEFORE aborting merge (after abort, they're hard to detect)
                conflicted = self._list_conflicts()
                if not conflicted:
                    # Fallback: try to find them from merge status
                    conflicted = self._list_conflicts_from_status()
                self._abort_merge()
                return SyncStatus(
                    status="conflicts",
                    message=f"Merge conflict detected in {len(conflicted)} file(s). Seshat refuses to auto-resolve.",
                    conflicted_files=conflicted,
                )

            # Other failure
            raise GitSyncError(
                f"git pull failed: {result.stderr or result.stdout}"
            )

        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"git pull crashed: {e.stderr.decode()}") from e

    def _list_conflicts(self) -> list[str]:
        """List files with merge conflicts using unmerged paths."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return [f for f in files if f]  # filter empty strings
        except subprocess.CalledProcessError:
            return []

    def _list_conflicts_from_status(self) -> list[str]:
        """Fallback: list conflicts from git status output."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            # Lines starting with UU, UD, DU, AA, DD, AU, UA, DD indicate conflicts
            conflicts = []
            for line in result.stdout.strip().split("\n"):
                if line and line[0:2] in ("UU", "UD", "DU", "AA", "DD", "AU", "UA"):
                    conflicts.append(line[3:])  # skip status prefix
            return conflicts
        except subprocess.CalledProcessError:
            return []

    def _abort_merge(self) -> None:
        """Abort an in-progress merge (called after conflict detection)."""
        try:
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # Merge may not be in progress, ignore

    def push(self, remote: str = "origin", branch: str = "main") -> str:
        """Push commits to remote. Returns status message."""
        try:
            result = subprocess.run(
                ["git", "push", remote, branch],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stderr or result.stdout or "Push successful"
        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"git push failed: {e.stderr.decode()}") from e

    def current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitSyncError(f"failed to get current branch: {e.stderr.decode()}") from e

    def log(self, max_count: int = 10) -> list[dict]:
        """Get recent commits. Returns list of {hash, message, author, timestamp}."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"-{max_count}",
                    "--format=%H%n%s%n%an%n%aI%n---",
                ],
                cwd=self.vault_root,
                check=True,
                capture_output=True,
                text=True,
            )

            commits = []
            lines = result.stdout.strip().split("\n")
            i = 0
            while i < len(lines):
                if i + 3 < len(lines):
                    commits.append(
                        {
                            "hash": lines[i][:7],  # short hash
                            "message": lines[i + 1],
                            "author": lines[i + 2],
                            "timestamp": lines[i + 3],
                        }
                    )
                    i += 5  # skip "---" marker
                else:
                    break
            return commits
        except subprocess.CalledProcessError:
            return []
