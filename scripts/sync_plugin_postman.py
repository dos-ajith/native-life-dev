import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MAIN_COLLECTION = ROOT / "postman" / "native-life-api.postman_collection.json"
PLUGIN_COLLECTION_GLOB = "plugins/*/*/postman/*.postman_collection.json"
REFERENCE_PREFIX = "_"
CORE_ENDPOINTS_MARKER = "(core endpoints)"
JSON_INDENT = 2
PLUGIN_CONTAINER_DEPTH = 2

Folder = dict[str, Any]


def load(path: Path) -> Folder:
    collection: Folder = json.loads(path.read_text(encoding="utf-8"))
    return collection


def write(path: Path, collection: Folder) -> None:
    text = json.dumps(collection, indent=JSON_INDENT, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def without_core_endpoints(folder: Folder) -> Folder:
    items = [
        without_core_endpoints(item) if "item" in item else item
        for item in folder["item"]
        if not (CORE_ENDPOINTS_MARKER in item["name"] and "item" in item)
    ]
    return {**folder, "item": items}


def find_folder(parent: Folder, name: str) -> Folder | None:
    return next((item for item in parent["item"] if item["name"] == name and "item" in item), None)


def replace_or_append(target: Folder, item: Folder) -> None:
    for index, existing in enumerate(target["item"]):
        if existing["name"] == item["name"]:
            target["item"][index] = item
            return
    target["item"].append(item)


def merge_folder(parent: Folder, folder: Folder, depth: int) -> None:
    existing = find_folder(parent, folder["name"])
    if existing is None:
        parent["item"].append(folder)
    elif depth == 0:
        replace_or_append(parent, folder)
    else:
        for child in folder["item"]:
            merge_folder(existing, child, depth - 1)


def merge_variables(main: Folder, plugin: Folder) -> None:
    known = {variable["key"] for variable in main.get("variable", [])}
    for variable in plugin.get("variable", []):
        if variable["key"] not in known:
            main.setdefault("variable", []).append(variable)


def main() -> None:
    collection = load(MAIN_COLLECTION)
    for path in sorted(ROOT.glob(PLUGIN_COLLECTION_GLOB)):
        if path.relative_to(ROOT).parts[1].startswith(REFERENCE_PREFIX):
            continue
        plugin = load(path)
        for group in plugin["item"]:
            merge_folder(collection, without_core_endpoints(group), PLUGIN_CONTAINER_DEPTH)
        merge_variables(collection, plugin)
    write(MAIN_COLLECTION, collection)


if __name__ == "__main__":
    main()
