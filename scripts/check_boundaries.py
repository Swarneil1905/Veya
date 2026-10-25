"""Owned-source dependency rules; imported skills and generated code are not scanned."""

import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path) -> list[str]:
    failures = []
    for path in (root / "services/runtime/veya/domain").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                if (
                    name.startswith("veya.") and not (name == "veya.domain" or name.startswith("veya.domain."))
                ) or name.split(".")[0] in {
                    "sqlite3",
                    "fastapi",
                    "httpx",
                    "requests",
                    "subprocess",
                }:
                    failures.append(
                        f"{path.relative_to(root)}:{node.lineno}: domain cannot import {name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.level > 1:
                failures.append(
                    f"{path.relative_to(root)}:{node.lineno}: domain cannot import parent adapters"
                )
    for path in (root / "apps/desktop/src").rglob("*.ts"):
        source = path.read_text(encoding="utf-8")
        imports = re.findall(
            r"(?:from\s*|import\s*\(\s*|import\s*)['\"]([^'\"]+)['\"]", source
        )
        for name in imports:
            if not (
                name.startswith(
                    ("@angular/", "rxjs", "@phosphor-icons/", "@fontsource")
                )
                or (
                    name.startswith(".")
                    and not re.search(
                        r"(?:services|secrets?|vault|src-tauri)(?:/|$)", name
                    )
                )
            ):
                failures.append(f"{path.relative_to(root)}: UI cannot import {name}")
        if re.search(r"\bimport\s*\(\s*[^'\"\s]", source):
            failures.append(
                f"{path.relative_to(root)}: UI imports must be statically bounded"
            )
    return failures


if __name__ == "__main__":
    errors = check(ROOT)
    print("\n".join(errors) if errors else "PASS: owned module boundaries")
    sys.exit(bool(errors))
