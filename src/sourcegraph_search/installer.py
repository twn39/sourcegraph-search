"""Administrative installer commands for sourcegraph-search CLI agent skills and configurations."""

from pathlib import Path
from typing import Optional

import typer

skills_app = typer.Typer(
    name="skills",
    help="Manage agent skills and configurations.",
    no_args_is_help=True,
)


def _get_resource_path(relative_path: str) -> Path:
    """Retrieve absolute path to a resource inside the package, or fallback to dev workspace."""
    # Packaged path (inside installed package under resources)
    path = Path(__file__).parent / "resources" / relative_path
    if path.exists():
        return path

    # Dev workspace fallback 1 (relative to project root)
    fallback = (
        Path(__file__).parent.parent.parent
        / "src"
        / "sourcegraph_search"
        / "resources"
        / relative_path
    )
    if fallback.exists():
        return fallback

    # Dev workspace fallback 2 (direct relative path from root)
    fallback_root = Path(__file__).parent.parent.parent / relative_path
    if fallback_root.exists():
        return fallback_root

    raise FileNotFoundError(
        f"Resource {relative_path} not found in package or workspace."
    )


@skills_app.command("install")
def install_skills(
    ctx: typer.Context,
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Target CLI agents to install the skills to. Options: all, codex, antigravity, crush, claude. (default: all)",
    ),
    global_install: bool = typer.Option(
        True,
        "--global/--local",
        help="Install globally (user-level) or locally (project-level).",
    ),
) -> None:
    """Install sourcegraph-search agent skills to supported CLI agents."""
    targets = ["codex", "antigravity", "crush", "claude"]
    if target:
        requested = [t.strip().lower() for t in target.split(",")]
        if "all" not in requested:
            targets = [t for t in targets if t in requested]
            if not targets:
                typer.secho(
                    "Error: No valid target specified. Choose from: codex, antigravity, crush, claude, all",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)

    try:
        skill_src = _get_resource_path("skills/sourcegraph-search-skill/SKILL.md")
    except Exception as e:
        typer.secho(f"Error finding source files: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    skill_content = skill_src.read_text(encoding="utf-8")

    home = Path("~").expanduser()
    cwd = Path.cwd()

    # Codex
    if "codex" in targets:
        codex_base = home / ".codex" if global_install else cwd / ".codex"
        skill_dst = codex_base / "skills" / "sourcegraph-search-skill" / "SKILL.md"
        try:
            skill_dst.parent.mkdir(parents=True, exist_ok=True)
            skill_dst.write_text(skill_content, encoding="utf-8")
            typer.secho(f"Installed Codex Skill to: {skill_dst}", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(
                f"Failed to install Codex skills: {e}", fg=typer.colors.RED, err=True
            )

    # Antigravity
    if "antigravity" in targets:
        antigravity_base = (
            home / ".gemini" / "config" if global_install else cwd / ".agents"
        )
        skill_dst = (
            antigravity_base / "skills" / "sourcegraph-search-skill" / "SKILL.md"
        )
        try:
            skill_dst.parent.mkdir(parents=True, exist_ok=True)
            skill_dst.write_text(skill_content, encoding="utf-8")
            typer.secho(
                f"Installed Antigravity Skill to: {skill_dst}", fg=typer.colors.GREEN
            )
        except Exception as e:
            typer.secho(
                f"Failed to install Antigravity skills: {e}",
                fg=typer.colors.RED,
                err=True,
            )

    # Crush
    if "crush" in targets:
        try:
            if global_install:
                crush_paths = [
                    home
                    / ".config"
                    / "crush"
                    / "skills"
                    / "sourcegraph-search-skill"
                    / "SKILL.md",
                    home
                    / ".config"
                    / "agents"
                    / "skills"
                    / "sourcegraph-search-skill"
                    / "SKILL.md",
                    home
                    / ".agents"
                    / "skills"
                    / "sourcegraph-search-skill"
                    / "SKILL.md",
                ]
            else:
                crush_paths = [
                    cwd / ".crush" / "skills" / "sourcegraph-search-skill" / "SKILL.md",
                    cwd
                    / ".agents"
                    / "skills"
                    / "sourcegraph-search-skill"
                    / "SKILL.md",
                ]
            for skill_dst in crush_paths:
                skill_dst.parent.mkdir(parents=True, exist_ok=True)
                skill_dst.write_text(skill_content, encoding="utf-8")
                typer.secho(
                    f"Installed Crush Skill to: {skill_dst}", fg=typer.colors.GREEN
                )
        except Exception as e:
            typer.secho(
                f"Failed to install Crush skills: {e}", fg=typer.colors.RED, err=True
            )

    # Claude Code
    if "claude" in targets:
        claude_base = home / ".claude" if global_install else cwd / ".claude"
        skill_dst = claude_base / "skills" / "sourcegraph-search-skill" / "SKILL.md"
        try:
            skill_dst.parent.mkdir(parents=True, exist_ok=True)
            skill_dst.write_text(skill_content, encoding="utf-8")
            typer.secho(
                f"Installed Claude Code Skill to: {skill_dst}", fg=typer.colors.GREEN
            )
        except Exception as e:
            typer.secho(
                f"Failed to install Claude Code skills: {e}",
                fg=typer.colors.RED,
                err=True,
            )
