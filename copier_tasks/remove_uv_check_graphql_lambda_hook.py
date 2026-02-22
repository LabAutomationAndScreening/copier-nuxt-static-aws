from __future__ import annotations

import sys
from pathlib import Path


def remove_hook_block(config_path: Path, hook_id: str) -> bool:
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    output_lines: list[str] = []
    index = 0
    removed = False

    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indentation = len(line) - len(stripped)

        if stripped.startswith(f"- id: {hook_id}"):
            removed = True
            index += 1
            while index < len(lines):
                next_line = lines[index]
                next_stripped = next_line.lstrip()
                next_indentation = len(next_line) - len(next_stripped)
                if next_stripped.startswith("- id:") and next_indentation == indentation:
                    break
                if next_stripped and next_indentation < indentation:
                    break
                index += 1
            continue

        output_lines.append(line)
        index += 1

    if not removed:
        return False

    trailing_newline = "\n" if text.endswith("\n") else ""
    _ = config_path.write_text("\n".join(output_lines) + trailing_newline, encoding="utf-8")
    return True


def main() -> int:
    target_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".pre-commit-config.yaml")
    hook_id = "uv-check-graphql-lambda"

    if not target_file.exists():
        print(f"{target_file} not found; skipping graphql-lambda hook removal.")
        return 0

    removed = remove_hook_block(target_file, hook_id)
    if removed:
        print(f"Removed hook '{hook_id}' from {target_file}.")
    else:
        print(f"Hook '{hook_id}' not found in {target_file}; no changes made.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
