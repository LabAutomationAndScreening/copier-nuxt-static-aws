from __future__ import annotations

import sys
import re
from pathlib import Path


HOOK_ID_LINE = re.compile(r"^-\s+id:\s")
_GRAPHQL_LAMBDA_ID = re.compile(r"-\s+id:\s+(graphql[_-]lambda)")


def _is_graphql_lambda_hook_block(block_lines: list[str]) -> bool:
    return bool(_GRAPHQL_LAMBDA_ID.search(block_lines[0])) if block_lines else False


def remove_graphql_lambda_hook_blocks(config_path: Path) -> int:
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    output_lines: list[str] = []
    index = 0
    removed_count = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indentation = len(line) - len(stripped)

        if HOOK_ID_LINE.match(stripped):
            block_start = index
            block_end = index + 1

            while block_end < len(lines):
                next_line = lines[block_end]
                next_stripped = next_line.lstrip()
                next_indentation = len(next_line) - len(next_stripped)
                if HOOK_ID_LINE.match(next_stripped) and next_indentation == indentation:
                    break
                if next_stripped and next_indentation < indentation:
                    break
                block_end += 1

            block_lines = lines[block_start:block_end]
            if _is_graphql_lambda_hook_block(block_lines):
                removed_count += 1
                index = block_end
                continue

            output_lines.extend(block_lines)
            index = block_end
            continue

        output_lines.append(line)
        index += 1

    if removed_count == 0:
        return 0

    trailing_newline = "\n" if text.endswith("\n") else ""
    _ = config_path.write_text("\n".join(output_lines) + trailing_newline, encoding="utf-8")
    return removed_count


def main() -> int:
    target_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".pre-commit-config.yaml")

    if not target_file.exists():
        print(f"{target_file} not found; skipping graphql_lambda hook removal.")
        return 0

    removed_count = remove_graphql_lambda_hook_blocks(target_file)
    if removed_count > 0:
        print(f"Removed {removed_count} graphql_lambda-related hook(s) from {target_file}.")
    else:
        print(f"No graphql_lambda-related hooks found in {target_file}; no changes made.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
