import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import SOURCE_SUFFIXES, FileFinder, ModuleSpec, SourceFileLoader
from types import CodeType, ModuleType


class SourceOnlyLoader(SourceFileLoader):
    def get_code(self, fullname: str) -> CodeType:
        path = self.get_filename(fullname)
        return self.source_to_code(self.get_data(path), path)


class PluginSourceFinder(MetaPathFinder):
    def __init__(self, package_prefix: str) -> None:
        self.package_prefix = package_prefix

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if path is None or not fullname.startswith(self.package_prefix):
            return None
        for entry in path:
            spec = FileFinder(entry, (SourceOnlyLoader, SOURCE_SUFFIXES)).find_spec(
                fullname, target
            )
            if spec is not None and spec.loader is not None:
                return spec
        return None


def install_plugin_source_finder(package_prefix: str) -> None:
    installed = any(
        isinstance(finder, PluginSourceFinder) and finder.package_prefix == package_prefix
        for finder in sys.meta_path
    )
    if not installed:
        sys.meta_path.insert(0, PluginSourceFinder(package_prefix))
