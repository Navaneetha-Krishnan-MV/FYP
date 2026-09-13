from pathlib import Path

EXCLUDED = {".git", ".env", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", "target"}


def allowed_source(root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
        return (not path.is_symlink() and not any(p in EXCLUDED or p.startswith(".env") for p in relative.parts)
                and path.is_file() and path.stat().st_size <= 1_000_000)
    except (OSError, ValueError):
        return False
