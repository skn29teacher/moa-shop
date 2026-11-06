"""Build a source-only PythonAnywhere ZIP using Python's standard library."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "moashop-sqlite-deploy.zip"
ROOT_FILES = ("wsgi.py", "requirements.txt", ".env.example", "sql/schema.sql", "sql/seed.sql",
              "sql/migrations/002_chat_history.sql")
FOLDERS = ("app", "templates", "static", "knowledge")
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".db", ".sqlite", ".sqlite3",
                     ".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".bin"}


def source_files():
    files = [ROOT / name for name in ROOT_FILES]
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Missing or invalid required file: {path.relative_to(ROOT)}")
    for folder in FOLDERS:
        base = ROOT / folder
        if not base.is_dir() or base.is_symlink():
            raise RuntimeError(f"Missing or invalid source directory: {folder}")
        for path in base.rglob("*"):
            relative = path.relative_to(ROOT)
            if any(part.startswith(".") or part in {"__pycache__", "node_modules"} for part in relative.parts):
                continue
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != ROOT):
                continue
            if not path.is_file() or not path.resolve().is_relative_to(ROOT):
                continue
            if path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if folder == "app" and path.suffix != ".py":
                continue
            if folder == "knowledge" and path.suffix.lower() not in {".md", ".txt", ".example"}:
                continue
            files.append(path)
    return sorted(set(files))


def main():
    files = source_files()
    OUTPUT.parent.mkdir(exist_ok=True)
    temporary = OUTPUT.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
            if temporary.stat().st_size >= 100 * 1024 * 1024:
                raise RuntimeError("ZIP exceeds the 100 MiB upload limit")
        temporary.replace(OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Created: {OUTPUT}")
    print(f"Files: {len(files)} | Size: {OUTPUT.stat().st_size:,} bytes")
    print("Excluded: real .env, databases, virtualenvs, Git, tests, caches and model weights.")


if __name__ == "__main__":
    main()
