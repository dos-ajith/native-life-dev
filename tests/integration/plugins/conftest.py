from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.core.permissions import RoleSlug
from app.core.timezone import app_now
from app.main import app
from app.models.business import Business, BusinessStatus
from app.models.category import Category, CategoryStatus
from app.models.plugin import Plugin, PluginStatus
from app.models.role import Role
from app.models.user import User
from app.models.user_has_role import user_has_roles
from app.plugins.discovery import discover_plugins
from app.plugins.loader import LoadedPlugin
from app.plugins.manifest import PluginManifest
from app.plugins.registry import PluginRegistry
from app.services.plugin_installation_service import ApplyResult, PluginInstallationService
from scripts.seed import seed_roles_and_permissions
from tests.integration.conftest import UserFactory, bearer, login

PLUGIN_CODE = """
from app.plugins.sdk import PluginContext


def register(ctx: PluginContext) -> None:
    pass
"""


@pytest.fixture(autouse=True)
def seeded_roles(clean_database: None) -> None:
    seed_roles_and_permissions()


@dataclass
class Actor:
    user: User
    headers: dict[str, str]


ActorFactory = Callable[..., Actor]


def _add_role(user_id: UUID, slug: str, verified: bool) -> None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        role = session.scalar(select(Role).where(Role.slug == slug))
        assert user is not None and role is not None
        user.roles.append(role)
        session.commit()
        if verified:
            session.execute(
                update(user_has_roles)
                .where(user_has_roles.c.user_id == user_id, user_has_roles.c.role_id == role.id)
                .values(verified_at=app_now())
            )
            session.commit()


@pytest.fixture
def actor(client: TestClient, make_user: UserFactory) -> ActorFactory:
    def factory(kind: str = "provider") -> Actor:
        base_role = RoleSlug.SUPER_ADMIN if kind == "super_admin" else RoleSlug.INDIVIDUAL_USER
        user = make_user(role_slug=base_role)
        if kind in ("provider", "pending_provider"):
            _add_role(user.id, RoleSlug.BUSINESS_SERVICE_PROVIDER, verified=kind == "provider")
        assert user.email is not None
        return Actor(user=user, headers=bearer(login(client, user.email)["access_token"]))

    return factory


def category_by_slug(slug: str) -> Category:
    with SessionLocal() as session:
        category = session.scalar(select(Category).where(Category.slug == slug))
        assert category is not None, slug
        session.expunge(category)
        return category


def add_category(
    name: str,
    parent_slug: str | None,
    slug: str | None = None,
    status: CategoryStatus = CategoryStatus.PUBLISHED,
    is_active: bool = True,
) -> Category:
    parent_id = category_by_slug(parent_slug).id if parent_slug is not None else None
    with SessionLocal() as session:
        category = Category(
            id=uuid4(),
            parent_id=parent_id,
            name=name,
            slug=slug or f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
            status=status,
            is_active=is_active,
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        session.expunge(category)
        return category


def add_business(
    owner: User,
    category_slug: str | None,
    status: BusinessStatus = BusinessStatus.ACTIVE,
    deleted: bool = False,
) -> Business:
    category_id = category_by_slug(category_slug).id if category_slug is not None else None
    with SessionLocal() as session:
        business = Business(
            owner_id=owner.id,
            category_id=category_id,
            name=f"Shop {uuid4().hex[:6]}",
            status=status,
            deleted_at=app_now() if deleted else None,
        )
        session.add(business)
        session.commit()
        session.refresh(business)
        session.expunge(business)
        return business


def plugin_manifest(
    key: str,
    *,
    version: str = "1.0.0",
    business_type: str = "service",
    categories: str = "[]",
    capabilities: str = "",
    permissions: tuple[str, ...] = (),
) -> str:
    permission_tables = "".join(
        f'\n[permissions."{name}"]\ndescription = "Permission {name}"\n' for name in permissions
    )
    return (
        dedent(
            f"""
            manifest_version = 1
            dependencies = []
            categories = {categories}

            [plugin]
            key = "{key}"
            name = "Plugin {key}"
            version = "{version}"
            role_scope = "business-service-provider"
            business_type = "{business_type}"

            [compatibility]
            core_api = ">=1.1,<2.0"

            [api]
            prefix = "/plugins/{key}"
            tag = "1.5 Businesses · {key}"

            [database]
            table_prefix = "plg_{key}_"
            """
        )
        + permission_tables
        + dedent(capabilities)
    )


@dataclass
class PluginWorkspace:
    root: Path

    def write(self, key: str, manifest: str) -> Path:
        directory = self.root / key
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("")
        (directory / "plugin.py").write_text(dedent(PLUGIN_CODE))
        (directory / "plugin.toml").write_text(manifest, encoding="utf-8")
        return directory

    def apply(self, *keys: str) -> dict[str | None, ApplyResult]:
        with SessionLocal() as session:
            service = PluginInstallationService(session, smoke_loader=lambda _root: None)
            results = service.apply(discover_plugins(self.root), set(keys))
        return {result.key: result for result in results}


@pytest.fixture
def workspace(tmp_path: Path) -> PluginWorkspace:
    directory = tmp_path / "plugins"
    directory.mkdir()
    return PluginWorkspace(directory)


def set_plugin_status(key: str, status: PluginStatus) -> None:
    with SessionLocal() as session:
        plugin = session.scalar(select(Plugin).where(Plugin.key == key))
        assert plugin is not None
        plugin.status = status
        session.commit()


def registry_for(*keys: str) -> PluginRegistry:
    with SessionLocal() as session:
        plugins = session.scalars(select(Plugin).where(Plugin.key.in_(keys))).all()
        return PluginRegistry(
            plugins=tuple(
                LoadedPlugin(
                    manifest=PluginManifest.model_validate(plugin.manifest),
                    root=Path(plugin.key),
                    content_sha256=plugin.content_sha256,
                    routers=(),
                    model_bases=(),
                )
                for plugin in plugins
            )
        )


@pytest.fixture
def use_registry() -> Iterator[Callable[..., None]]:
    previous = getattr(app.state, "plugin_registry", None)

    def install(*keys: str) -> None:
        app.state.plugin_registry = registry_for(*keys)

    yield install
    app.state.plugin_registry = previous
