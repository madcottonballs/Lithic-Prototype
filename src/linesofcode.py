"""A simple script to count the number of lines of code in this project, excluding comments and blank lines. This can be useful for tracking progress or estimating the size of the codebase."""
from pathlib import Path


def count_code_lines_in_file(file_path: Path) -> int:
    count = 0
    with file_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            count += 1
    return count


def main() -> None:
    root = Path(__file__).resolve().parent
    total = 0

    for file_path in root.rglob("*.py"):
        if any(part in {"__pycache__", ".git"} for part in file_path.parts):
            continue
        total += count_code_lines_in_file(file_path)

    print(total)


if __name__ == "__main__":
    main()
