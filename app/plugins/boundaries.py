import ast
import sys
from collections.abc import Iterator
from importlib.metadata import packages_distributions
from pathlib import Path

from app.core.messages import PluginMessages
from app.plugins.layout import TESTS_DIRECTORY, UNVERIFIED_DIRECTORIES

CORE_PACKAGE = "app"
SDK_MODULE = "app.plugins.sdk"
SDK_PARENT_MODULE, SDK_NAME = SDK_MODULE.rsplit(".", 1)
FORBIDDEN_CALL_NAME = "backref"
FORBIDDEN_KEYWORD = "backref"
FORBIDDEN_OVERRIDES_NAME = "dependency_overrides"


def _is_excluded(path: Path, root: Path) -> bool:
    return any(part in UNVERIFIED_DIRECTORIES for part in path.relative_to(root).parts)


def plugin_source_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if not _is_excluded(path, root))


def importable_top_level_modules() -> frozenset[str]:
    return frozenset(sys.stdlib_module_names) | frozenset(packages_distributions())


def _is_core_module(module: str) -> bool:
    return module == CORE_PACKAGE or module.startswith(f"{CORE_PACKAGE}.")


def _is_allowed_absolute(module: str, imported_names: list[str], allowed: frozenset[str]) -> bool:
    if _is_core_module(module):
        if module == SDK_MODULE:
            return True
        return module == SDK_PARENT_MODULE and all(name == SDK_NAME for name in imported_names)
    return module.split(".")[0] in allowed


def _forbidden_absolute_imports(node: ast.AST, allowed: frozenset[str]) -> Iterator[str]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            if not _is_allowed_absolute(alias.name, [], allowed):
                yield alias.name
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
        names = [alias.name for alias in node.names]
        if not _is_allowed_absolute(node.module, names, allowed):
            yield node.module


def _unverified_import_directory(node: ast.AST, package_parts: tuple[str, ...]) -> str | None:
    if not isinstance(node, ast.ImportFrom) or node.level == 0:
        return None
    if node.level - 1 > len(package_parts):
        return None
    base = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        targets = [base + tuple(node.module.split("."))]
    else:
        targets = [base + (alias.name,) for alias in node.names]
    return next(
        (part for target in targets for part in target if part in UNVERIFIED_DIRECTORIES), None
    )


def _unverified_import_violation(directory: str, file: str, line: int) -> str:
    if directory == TESTS_DIRECTORY:
        return PluginMessages.FORBIDDEN_TESTS_IMPORT.format(file=file, line=line)
    return PluginMessages.FORBIDDEN_UNVERIFIED_IMPORT.format(
        file=file, line=line, directory=directory
    )


def _uses_backref(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    called_name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
    if called_name == FORBIDDEN_CALL_NAME:
        return True
    return any(keyword.arg == FORBIDDEN_KEYWORD for keyword in node.keywords)


def _mentions_dependency_overrides(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return FORBIDDEN_OVERRIDES_NAME in node.attr
    if isinstance(node, ast.Name):
        return FORBIDDEN_OVERRIDES_NAME in node.id
    if isinstance(node, ast.alias):
        return any(FORBIDDEN_OVERRIDES_NAME in name for name in (node.name, node.asname or ""))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return FORBIDDEN_OVERRIDES_NAME in node.value
    return False


def _file_violations(path: Path, root: Path, allowed: frozenset[str]) -> list[str]:
    relative_path = path.relative_to(root)
    relative = relative_path.as_posix()
    try:
        tree = ast.parse(path.read_bytes(), filename=relative)
    except SyntaxError as exc:
        return [
            PluginMessages.SOURCE_SYNTAX_ERROR.format(file=relative, line=exc.lineno, error=exc.msg)
        ]
    package_parts = relative_path.parent.parts
    violations: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        violations.extend(
            PluginMessages.FORBIDDEN_IMPORT.format(file=relative, line=line, module=module)
            for module in _forbidden_absolute_imports(node, allowed)
        )
        unverified = _unverified_import_directory(node, package_parts)
        if unverified is not None:
            violations.append(_unverified_import_violation(unverified, relative, line))
        if _uses_backref(node):
            violations.append(PluginMessages.FORBIDDEN_BACKREF.format(file=relative, line=line))
        if _mentions_dependency_overrides(node):
            violations.append(
                PluginMessages.FORBIDDEN_DEPENDENCY_OVERRIDES.format(file=relative, line=line)
            )
    return violations


def find_boundary_violations(root: Path) -> list[str]:
    allowed = importable_top_level_modules()
    return [
        violation
        for path in plugin_source_files(root)
        for violation in _file_violations(path, root, allowed)
    ]
