import re
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import String
from sqlalchemy.sql.elements import KeyedColumnElement

from app.core.business_categories import BUSINESS_TYPE_ROOT_SLUGS, BusinessCategorySlug
from app.core.messages import PluginMessages
from app.core.permissions import RoleSlug
from app.models.category import Category
from app.models.permission import Permission
from app.models.plugin import (
    PLUGIN_KEY_MAX_LENGTH,
    PLUGIN_VERSION_MAX_LENGTH,
    PluginBusinessType,
)
from app.plugins.errors import PluginError
from app.plugins.layout import UNVERIFIED_DIRECTORIES
from app.plugins.versioning import Version, VersionRange

MANIFEST_FILENAME = "plugin.toml"
ALLOWED_ROLE_SCOPE = RoleSlug.BUSINESS_SERVICE_PROVIDER
PLUGIN_API_TAG_PREFIX = "1.5 Businesses · "
CAPABILITY_PATH_PLACEHOLDER = "{business_id}"

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_KEY_MIN_LENGTH = 3
_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
_MODULE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*$")
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CAPABILITY_PATH_PATTERN = re.compile(r"^(?:/(?:[a-z0-9][a-z0-9_-]*|\{business_id\}))+$")
_PERMISSION_SUFFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_PATH_SEGMENT = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
_RELATIVE_PATH_PATTERN = re.compile(rf"^{_PATH_SEGMENT}(?:/{_PATH_SEGMENT})*$")
_RELATIVE_PATH_MAX_LENGTH = 200


def _string_length(column: KeyedColumnElement[Any]) -> int:
    column_type = column.type
    if not isinstance(column_type, String) or column_type.length is None:
        raise TypeError(column.key)
    return column_type.length


_PERMISSION_NAME_MAX_LENGTH = _string_length(Permission.__table__.c.name)
_PERMISSION_DESCRIPTION_MAX_LENGTH = _string_length(Permission.__table__.c.description)
_CATEGORY_NAME_MAX_LENGTH = _string_length(Category.__table__.c.name)
_CATEGORY_SLUG_MAX_LENGTH = _string_length(Category.__table__.c.slug)


def _validate_key(value: str) -> str:
    has_valid_length = _KEY_MIN_LENGTH <= len(value) <= PLUGIN_KEY_MAX_LENGTH
    if not has_valid_length or not _KEY_PATTERN.match(value):
        raise ValueError(PluginMessages.INVALID_KEY)
    return value


def _validate_version(value: str) -> str:
    Version.parse(value)
    return value


def _validate_version_range(value: str) -> str:
    VersionRange.parse(value)
    return value


def _validate_slug(value: str) -> str:
    if not _SLUG_PATTERN.match(value):
        raise ValueError(PluginMessages.INVALID_SLUG.format(value=value))
    return value


def _validate_pattern(pattern: re.Pattern[str]) -> AfterValidator:
    def validate(value: str) -> str:
        if not pattern.match(value):
            raise ValueError(PluginMessages.INVALID_IDENTIFIER.format(value=value))
        return value

    return AfterValidator(validate)


PluginKey = Annotated[str, AfterValidator(_validate_key)]
SemanticVersion = Annotated[
    str, Field(max_length=PLUGIN_VERSION_MAX_LENGTH), AfterValidator(_validate_version)
]
VersionRangeText = Annotated[str, AfterValidator(_validate_version_range)]
CategorySlug = Annotated[
    str, Field(max_length=_CATEGORY_SLUG_MAX_LENGTH), AfterValidator(_validate_slug)
]


class _ManifestSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PluginInfo(_ManifestSection):
    key: PluginKey
    name: Annotated[str, Field(min_length=1, max_length=100)]
    version: SemanticVersion
    role_scope: str
    business_type: PluginBusinessType
    description: Annotated[str, Field(max_length=500)] | None = None


class CompatibilityConfig(_ManifestSection):
    core_api: VersionRangeText


class DependencyDeclaration(_ManifestSection):
    key: PluginKey
    version: VersionRangeText
    optional: bool = False

    @property
    def version_range(self) -> VersionRange:
        return VersionRange.parse(self.version)


class CategoryDeclaration(_ManifestSection):
    slug: CategorySlug
    name: Annotated[str, Field(min_length=1, max_length=_CATEGORY_NAME_MAX_LENGTH)]
    parent: CategorySlug
    bind: bool = False
    include_descendants: bool = False


def _validate_entry_module(value: str) -> str:
    package = next((part for part in value.split(".") if part in UNVERIFIED_DIRECTORIES), None)
    if package is not None:
        raise ValueError(PluginMessages.ENTRYPOINT_IN_EXCLUDED_PACKAGE.format(package=package))
    return value


def _validate_relative_path(value: str) -> str:
    is_safe = _RELATIVE_PATH_PATTERN.match(value) and not any(
        part in UNVERIFIED_DIRECTORIES for part in value.split("/")
    )
    if not is_safe:
        raise ValueError(PluginMessages.INVALID_UI_PATH.format(value=value))
    return value


RelativePath = Annotated[
    str, Field(max_length=_RELATIVE_PATH_MAX_LENGTH), AfterValidator(_validate_relative_path)
]


class EntrypointConfig(_ManifestSection):
    module: Annotated[
        str, _validate_pattern(_MODULE_PATTERN), AfterValidator(_validate_entry_module)
    ] = "plugin"
    function: Annotated[str, _validate_pattern(_IDENTIFIER_PATTERN)] = "register"


class ApiConfig(_ManifestSection):
    prefix: str
    tag: Annotated[str, Field(max_length=100)]


class DatabaseConfig(_ManifestSection):
    table_prefix: str
    migrations: bool = False
    seeders: bool = False


class UiBundleConfig(_ManifestSection):
    path: RelativePath
    entry: RelativePath


class PermissionDeclaration(_ManifestSection):
    description: Annotated[str, Field(min_length=1, max_length=_PERMISSION_DESCRIPTION_MAX_LENGTH)]


class CapabilityType(StrEnum):
    MENU = "menu"
    WIDGET = "widget"


def _validate_capability_path(value: str) -> str:
    if not _CAPABILITY_PATH_PATTERN.match(value):
        raise ValueError(PluginMessages.INVALID_CAPABILITY_PATH.format(path=value))
    return value


class CapabilityDeclaration(_ManifestSection):
    key: Annotated[str, _validate_pattern(_IDENTIFIER_PATTERN)]
    title: Annotated[str, Field(min_length=1, max_length=100)]
    type: CapabilityType
    path: Annotated[str, Field(max_length=200), AfterValidator(_validate_capability_path)]
    permission: str


class PluginManifest(_ManifestSection):
    manifest_version: Literal[1]
    plugin: PluginInfo
    compatibility: CompatibilityConfig
    dependencies: tuple[DependencyDeclaration, ...]
    categories: tuple[CategoryDeclaration, ...]
    entrypoint: EntrypointConfig = EntrypointConfig()
    api: ApiConfig
    database: DatabaseConfig
    permissions: dict[str, PermissionDeclaration] = Field(default_factory=dict)
    capabilities: tuple[CapabilityDeclaration, ...] = ()
    frontend: UiBundleConfig | None = None
    admin_panel: UiBundleConfig | None = None

    @property
    def key(self) -> str:
        return self.plugin.key

    @property
    def version(self) -> Version:
        return Version.parse(self.plugin.version)

    @property
    def core_api(self) -> VersionRange:
        return VersionRange.parse(self.compatibility.core_api)

    @property
    def required_dependency_keys(self) -> tuple[str, ...]:
        return tuple(dependency.key for dependency in self.dependencies if not dependency.optional)

    @property
    def ui_bundles(self) -> dict[str, UiBundleConfig]:
        bundles = {"frontend": self.frontend, "admin_panel": self.admin_panel}
        return {section: bundle for section, bundle in bundles.items() if bundle is not None}

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        self._validate_role_scope()
        self._validate_api()
        self._validate_database()
        self._validate_permissions()
        self._validate_dependencies()
        self._validate_categories()
        self._validate_capabilities()
        return self

    def _validate_role_scope(self) -> None:
        if self.plugin.role_scope != ALLOWED_ROLE_SCOPE:
            raise ValueError(
                PluginMessages.INVALID_ROLE_SCOPE.format(role_scope=ALLOWED_ROLE_SCOPE)
            )

    def _validate_api(self) -> None:
        expected_prefix = f"/plugins/{self.key}"
        if self.api.prefix != expected_prefix:
            raise ValueError(PluginMessages.INVALID_API_PREFIX.format(expected=expected_prefix))
        if (
            not self.api.tag.startswith(PLUGIN_API_TAG_PREFIX)
            or self.api.tag == PLUGIN_API_TAG_PREFIX
        ):
            raise ValueError(PluginMessages.INVALID_API_TAG.format(prefix=PLUGIN_API_TAG_PREFIX))

    def _validate_database(self) -> None:
        expected_prefix = f"plg_{self.key}_"
        if self.database.table_prefix != expected_prefix:
            raise ValueError(PluginMessages.INVALID_TABLE_PREFIX.format(expected=expected_prefix))

    def _validate_permissions(self) -> None:
        namespace = f"plugin.{self.key}."
        for name in self.permissions:
            suffix = name.removeprefix(namespace)
            if (
                suffix == name
                or not _PERMISSION_SUFFIX_PATTERN.match(suffix)
                or len(name) > _PERMISSION_NAME_MAX_LENGTH
            ):
                raise ValueError(
                    PluginMessages.INVALID_PERMISSION_NAME.format(
                        name=name, key=self.key, max_length=_PERMISSION_NAME_MAX_LENGTH
                    )
                )

    def _validate_dependencies(self) -> None:
        seen: set[str] = set()
        for dependency in self.dependencies:
            if dependency.key == self.key:
                raise ValueError(PluginMessages.SELF_DEPENDENCY)
            if dependency.key in seen:
                raise ValueError(PluginMessages.DUPLICATE_DEPENDENCY.format(key=dependency.key))
            seen.add(dependency.key)

    def _validate_categories(self) -> None:
        root = BUSINESS_TYPE_ROOT_SLUGS[self.plugin.business_type]
        known_parents = {root}
        declared: set[str] = set()
        for category in self.categories:
            if category.slug in declared:
                raise ValueError(PluginMessages.DUPLICATE_CATEGORY_SLUG.format(slug=category.slug))
            declared.add(category.slug)
            if category.slug == root:
                if category.parent != BusinessCategorySlug.ROOT:
                    raise ValueError(
                        PluginMessages.INVALID_ROOT_DECLARATION.format(
                            slug=root,
                            business_type=self.plugin.business_type.value,
                            parent=BusinessCategorySlug.ROOT,
                        )
                    )
                continue
            if not category.slug.startswith(f"{root}-"):
                raise ValueError(
                    PluginMessages.INVALID_CATEGORY_SLUG.format(
                        slug=category.slug, prefix=f"{root}-"
                    )
                )
            if category.parent not in known_parents:
                raise ValueError(
                    PluginMessages.UNKNOWN_CATEGORY_PARENT.format(
                        slug=category.slug, parent=category.parent, root=root
                    )
                )
            known_parents.add(category.slug)

    def _validate_capabilities(self) -> None:
        seen: set[str] = set()
        for capability in self.capabilities:
            if capability.key in seen:
                raise ValueError(PluginMessages.DUPLICATE_CAPABILITY_KEY.format(key=capability.key))
            seen.add(capability.key)
            if capability.permission not in self.permissions:
                raise ValueError(
                    PluginMessages.UNKNOWN_CAPABILITY_PERMISSION.format(
                        key=capability.key, permission=capability.permission
                    )
                )


def _format_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'manifest'}: "
        f"{str(error['msg']).removeprefix('Value error, ')}"
        for error in exc.errors()
    )


def parse_manifest(content: bytes) -> PluginManifest:
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PluginError(PluginMessages.MANIFEST_UNREADABLE.format(error=exc)) from exc
    try:
        return PluginManifest.model_validate(data)
    except ValidationError as exc:
        raise PluginError(
            PluginMessages.MANIFEST_INVALID.format(errors=_format_validation_error(exc))
        ) from exc


def load_manifest(path: Path) -> PluginManifest:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise PluginError(PluginMessages.MANIFEST_UNREADABLE.format(error=exc)) from exc
    return parse_manifest(content)
