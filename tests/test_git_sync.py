"""Tests for git sync protocol."""

import subprocess
from pathlib import Path

import pytest

from seshat.core.git_sync import ConflictDetectedError, GitSyncError, GitVault, SyncStatus


@pytest.fixture
def vault_repo(tmp_path):
    """Create a git-initialized vault."""
    vault = GitVault(tmp_path)
    vault.init()
    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return vault


@pytest.fixture
def remote_repo(tmp_path):
    """Create a bare remote repository."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(
        ["git", "init", "--bare"],
        cwd=remote,
        check=True,
        capture_output=True,
    )
    return remote


class TestGitVaultInit:
    def test_init_creates_git_repo(self, tmp_path):
        vault = GitVault(tmp_path)
        assert not vault.is_initialized()
        vault.init()
        assert vault.is_initialized()

    def test_init_idempotent(self, vault_repo):
        assert vault_repo.is_initialized()
        vault_repo.init()  # should not raise
        assert vault_repo.is_initialized()

    def test_init_fails_on_nonexistent_root(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(GitSyncError, match="vault root not found"):
            GitVault(nonexistent)


class TestRemote:
    def test_add_remote(self, vault_repo, remote_repo):
        vault_repo.add_remote("origin", str(remote_repo))
        result = subprocess.run(
            ["git", "remote", "-v"],
            cwd=vault_repo.vault_root,
            capture_output=True,
            text=True,
        )
        assert "origin" in result.stdout

    def test_add_remote_idempotent(self, vault_repo, remote_repo):
        url = str(remote_repo)
        vault_repo.add_remote("origin", url)
        vault_repo.add_remote("origin", url)  # should not raise


class TestCommit:
    def test_commit_creates_commit(self, vault_repo):
        (vault_repo.vault_root / "test.txt").write_text("hello")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        commit_hash = vault_repo.commit("Initial commit")
        assert commit_hash  # non-empty hash
        assert len(commit_hash) >= 7  # at least 7 chars

    def test_commit_fails_without_changes(self, vault_repo):
        with pytest.raises(GitSyncError, match="no changes"):
            vault_repo.commit("Empty commit")

    def test_has_changes_detects_untracked(self, vault_repo):
        (vault_repo.vault_root / "test.txt").write_text("hello")
        assert vault_repo.has_changes()

    def test_has_changes_detects_modified(self, vault_repo):
        test_file = vault_repo.vault_root / "test.txt"
        test_file.write_text("hello")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        vault_repo.commit("Initial")
        test_file.write_text("goodbye")
        assert vault_repo.has_changes()

    def test_has_changes_false_on_clean(self, vault_repo):
        test_file = vault_repo.vault_root / "test.txt"
        test_file.write_text("hello")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        vault_repo.commit("Initial")
        assert not vault_repo.has_changes()


class TestPush:
    def test_push_to_remote(self, vault_repo, remote_repo):
        vault_repo.add_remote("origin", str(remote_repo))
        (vault_repo.vault_root / "test.txt").write_text("hello")
        vault_repo.commit("Initial")
        vault_repo.push()

        # Verify remote has commit
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=remote_repo,
            capture_output=True,
            text=True,
        )
        assert "Initial" in result.stdout


class TestPull:
    def test_pull_clean_merge(self, tmp_path, remote_repo):
        """Test pulling when there are no conflicts."""
        # Set up remote with initial commit
        remote_clone = tmp_path / "remote_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(remote_clone)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        (remote_clone / "file.txt").write_text("initial")
        subprocess.run(
            ["git", "add", "file.txt"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )

        # Set up local clone and pull
        local = tmp_path / "local"
        local.mkdir()
        vault = GitVault(local)
        vault.init()
        vault.add_remote("origin", str(remote_repo))
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        status = vault.pull()
        assert status.status == "clean"
        assert not status.conflicted_files
        assert (local / "file.txt").read_text() == "initial"

    def test_pull_detects_conflict(self, tmp_path, remote_repo):
        """Test that pull detects conflicts and refuses to auto-resolve."""
        # Set up initial repo on remote
        remote_clone = tmp_path / "remote_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(remote_clone)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        # Create initial base file
        (remote_clone / "conflict.txt").write_text("initial\n")
        subprocess.run(
            ["git", "add", "conflict.txt"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )

        # Clone locally and make a commit
        local = tmp_path / "local"
        local.mkdir()
        vault = GitVault(local)
        vault.init()
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        vault.add_remote("origin", str(remote_repo))
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main", "origin/main"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        # Make local change
        (local / "conflict.txt").write_text("local change\n")
        subprocess.run(
            ["git", "add", "conflict.txt"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Local change"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        # Make conflicting change on remote
        (remote_clone / "conflict.txt").write_text("remote change\n")
        subprocess.run(
            ["git", "add", "conflict.txt"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Remote change"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=remote_clone,
            check=True,
            capture_output=True,
        )

        # Pull should detect conflict and refuse to resolve
        status = vault.pull()
        assert status.status == "conflicts"
        assert "conflict.txt" in status.conflicted_files
        assert "refuses to auto-resolve" in status.message

        # Verify merge was aborted (no CONFLICT markers in working tree)
        content = (local / "conflict.txt").read_text()
        assert "<<<<<<" not in content  # merge conflict marker


class TestCurrentBranch:
    def test_current_branch(self, vault_repo):
        # Create a file and commit so we're on main
        (vault_repo.vault_root / "test.txt").write_text("hello")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        vault_repo.commit("Initial")
        branch = vault_repo.current_branch()
        assert branch in ("main", "master")  # default branch name


class TestLog:
    def test_log_returns_recent_commits(self, vault_repo):
        (vault_repo.vault_root / "file1.txt").write_text("1")
        subprocess.run(
            ["git", "add", "file1.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        vault_repo.commit("First commit")

        (vault_repo.vault_root / "file2.txt").write_text("2")
        subprocess.run(
            ["git", "add", "file2.txt"],
            cwd=vault_repo.vault_root,
            check=True,
            capture_output=True,
        )
        vault_repo.commit("Second commit")

        log = vault_repo.log(max_count=2)
        assert len(log) == 2
        assert log[0]["message"] == "Second commit"
        assert log[1]["message"] == "First commit"
        assert "hash" in log[0]
        assert "author" in log[0]
        assert "timestamp" in log[0]
