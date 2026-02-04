"""Generate the code reference pages and navigation."""

import ast
from pathlib import Path
from typing import Iterator

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()
nav["Home"] = "index.md"

root = Path(__file__).parent.parent
src = root / "kalbio"


def make_reference(
    prefix: str, m_name: str, member_names: list[str] | None = None
) -> str:
    """Generate the mkdocstrings directive."""
    options = ["    options:"]
    if member_names is not None:
        if member_names:
            options.append("        members:")
            options.extend(f"            - {m}" for m in member_names)
        else:
            options.append("        members: []")
    else:
        options.append("        members: yes")

    return f"::: {prefix}.{m_name}\n" + "\n".join(options) + "\n"


def get_class_members(node: ast.ClassDef) -> list[str]:
    """Extract public method names from a class definition."""
    to_return: list[str] = []

    for child in node.body:
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and not child.name.startswith("_"):
            to_return.append(child.name)

    return to_return


def iter_definitions(ast_tree: ast.Module) -> Iterator[tuple[str, list[str] | None]]:
    """Yield top-level definitions (name, members) from the AST."""
    for node in ast_tree.body:
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                yield node.name, get_class_members(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node.name, None
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    yield target.id, None
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
                yield node.target.id, None
        elif hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            if not node.name.id.startswith("_"):
                yield node.name.id, None


for path in sorted(src.rglob("*.py")):
    module_path = path.relative_to(src).with_suffix("")
    doc_path = path.relative_to(src).with_suffix(".md")
    full_doc_path = Path("docs", doc_path)

    module_name = module_path.stem
    if all(part.startswith(("example", "_")) for part in module_path.parts):
        continue

    formatted_name = module_name.replace("_", " ").title()

    # Use the full module path for navigation to preserve hierarchy
    nav_parts = ["API Reference"] + [
        part.replace("_", " ").title() for part in module_path.parts
    ]
    nav[tuple(nav_parts)] = full_doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as f:
        f.write(f"# {formatted_name}\n\n")
        module_full_name = f"kalbio.{'.'.join(module_path.parts)}"
        f.write(make_reference("kalbio", module_name, []))

        try:
            with open(path, "r", encoding="utf-8") as f_source:
                tree = ast.parse(f_source.read())
        except (SyntaxError, UnicodeDecodeError):
            continue

        for name, members in iter_definitions(tree):
            f.write(make_reference(module_full_name, name, members))

    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to(root))

with mkdocs_gen_files.open("SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
