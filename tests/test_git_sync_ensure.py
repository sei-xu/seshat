"""Tests for GitVault.clone/commit_and_push and the ensure_synced() helper —
the pieces that let the vault live entirely in git on an ephemeral disk
(e.g. Render's free tier, no persistent volume)."""

import subprocess

import pytest

from seshat.core.git_sync import GitSyncError, GitVault, ensure_synced


def _configure_identity(path):
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)


@pytest.fixture
def remote_with_vault(tmp_path):
    """A bare remote repo seeded with a minimal vault on branch 'main'."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init"], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=seed, check=True, capture_output=True)
    _configure_identity(seed)
    for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
        (seed / folder).mkdir()
        (seed / folder / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Seed vault"], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=seed, check=True, capture_output=True)

    return remote


class TestClone:
    def test_clone_into_empty_dir(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.clone(str(remote_with_vault), branch="main")
        assert vault.is_initialized()
        assert (target / "01-Fragments").is_dir()

    def test_clone_refuses_non_empty_dir(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        (target / "existing.txt").write_text("hi")
        vault = GitVault(target)
        with pytest.raises(GitSyncError, match="not empty"):
            vault.clone(str(remote_with_vault), branch="main")

    def test_clone_refuses_if_already_initialized(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.init()
        with pytest.raises(GitSyncError, match="already has a git repo"):
            vault.clone(str(remote_with_vault), branch="main")

    def test_clone_sets_local_identity(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.clone(str(remote_with_vault), branch="main")
        result = subprocess.run(
            ["git", "config", "--get", "user.email"], cwd=target, capture_output=True, text=True
        )
        assert result.stdout.strip()


class TestCommitAndPush:
    def test_commit_and_push_returns_none_without_changes(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.clone(str(remote_with_vault), branch="main")
        assert vault.commit_and_push("no-op") is None

    def test_commit_and_push_pushes_new_file(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.clone(str(remote_with_vault), branch="main")

        (target / "01-Fragments" / "novo.md").write_text("---\ntitle: novo\n---\ncorpo")
        commit_hash = vault.commit_and_push("adiciona fragmento")
        assert commit_hash is not None

        result = subprocess.run(
            ["git", "log", "-1", "main", "--format=%s"], cwd=remote_with_vault, capture_output=True, text=True
        )
        assert "adiciona fragmento" in result.stdout


class TestEnsureSynced:
    def test_ensure_synced_no_remote_just_creates_dir(self, tmp_path):
        target = tmp_path / "vault"
        vault = ensure_synced(target, remote_url=None)
        assert target.is_dir()
        assert not vault.is_initialized()

    def test_ensure_synced_clones_fresh_empty_disk(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        vault = ensure_synced(target, remote_url=str(remote_with_vault), branch="main")
        assert vault.is_initialized()
        assert (target / "02-Projects").is_dir()

    def test_ensure_synced_pulls_when_already_a_repo(self, tmp_path, remote_with_vault):
        target = tmp_path / "vault"
        target.mkdir()
        vault = GitVault(target)
        vault.clone(str(remote_with_vault), branch="main")

        # Push a new commit to the remote from a second clone.
        other = tmp_path / "other"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(remote_with_vault), str(other)],
            check=True,
            capture_output=True,
        )
        _configure_identity(other)
        (other / "02-Projects" / "novo.txt").write_text("x")
        subprocess.run(["git", "add", "-A"], cwd=other, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Novo projeto"], cwd=other, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=other, check=True, capture_output=True)

        ensure_synced(target, remote_url=str(remote_with_vault), branch="main")
        assert (target / "02-Projects" / "novo.txt").is_file()

    def test_ensure_synced_raises_when_initial_clone_fails(self, tmp_path):
        target = tmp_path / "vault"
        with pytest.raises(GitSyncError):
            ensure_synced(target, remote_url="https://example.invalid/nonexistent.git", branch="main")
