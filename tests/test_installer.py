import pytest
from pathlib import Path
from typer.testing import CliRunner
from sourcegraph_search.cli import app

runner = CliRunner()


@pytest.fixture
def mock_dirs(tmp_path, monkeypatch):
    """Mock Path.cwd() and Path('~').expanduser() to isolate file writes."""
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    mock_cwd = tmp_path / "cwd"
    mock_cwd.mkdir()

    # Patch Path.cwd() to return mock_cwd
    monkeypatch.setattr(Path, "cwd", lambda: mock_cwd)

    # Patch expanduser to return mock_home
    original_expanduser = Path.expanduser

    def custom_expanduser(self):
        if str(self) == "~":
            return mock_home
        return original_expanduser(self)

    monkeypatch.setattr(Path, "expanduser", custom_expanduser)

    return {
        "home": mock_home,
        "cwd": mock_cwd,
    }


def test_install_skills_help():
    """Verify help command of skills."""
    result = runner.invoke(app, ["skills", "--help"])
    assert result.exit_code == 0
    assert "Manage agent skills and configurations." in result.stdout


def test_install_skills_invalid_target(mock_dirs):
    """Verify error on invalid target."""
    result = runner.invoke(app, ["skills", "install", "--target", "invalid_agent"])
    assert result.exit_code == 1
    output = result.stdout + getattr(result, "stderr", "")
    assert "Error: No valid target specified" in output


def test_install_skills_global_all(mock_dirs):
    """Test global installation to all default targets."""
    result = runner.invoke(app, ["skills", "install"])
    assert result.exit_code == 0

    home = mock_dirs["home"]

    # Verify Codex skill installed globally
    codex_skill = home / ".codex" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    assert codex_skill.exists()
    assert "name: sourcegraph-search-skill" in codex_skill.read_text()

    # Verify Antigravity skill installed globally
    antigravity_skill = (
        home / ".gemini" / "config" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    )
    assert antigravity_skill.exists()

    # Verify Crush skill installed globally
    crush_skill_1 = (
        home / ".config" / "crush" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    )
    assert crush_skill_1.exists()

    # Verify Claude Code skill installed globally
    claude_skill = home / ".claude" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    assert claude_skill.exists()


def test_install_skills_local_antigravity(mock_dirs):
    """Test local installation to just Antigravity."""
    result = runner.invoke(
        app, ["skills", "install", "--local", "--target", "antigravity"]
    )
    assert result.exit_code == 0

    cwd = mock_dirs["cwd"]
    home = mock_dirs["home"]

    # Antigravity skill should be installed in mock_cwd/.agents/
    antigravity_skill = (
        cwd / ".agents" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    )
    assert antigravity_skill.exists()

    # Codex skill should NOT be installed
    codex_skill = cwd / ".codex" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    assert not codex_skill.exists()
    codex_home_skill = (
        home / ".codex" / "skills" / "sourcegraph-search-skill" / "SKILL.md"
    )
    assert not codex_home_skill.exists()
