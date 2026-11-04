TESTS_DIRECTORY = "tests"
CACHE_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
BUILD_TOOL_DIRECTORIES = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".cache",
        ".parcel-cache",
        ".next",
        ".nuxt",
        ".turbo",
        ".svelte-kit",
        "htmlcov",
        ".idea",
        ".vscode",
    }
)
UNVERIFIED_DIRECTORIES = frozenset({TESTS_DIRECTORY}) | CACHE_DIRECTORIES | BUILD_TOOL_DIRECTORIES
GENERATED_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})
GENERATED_FILE_SUFFIXES = frozenset({".pyc", ".pyo"})
