from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg.errors
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import BusinessMessages, BusinessPluginMessages
from app.core.permissions import PermissionName, RoleSlug
from app.models.business import Business, BusinessStatus
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.permission import Permission
from app.models.plugin import Plugin, PluginBusinessType, PluginStatus
from app.models.role import Role
from app.models.user import User
from app.plugins.loader import LoadedPlugin
from app.plugins.manifest import parse_manifest
from app.plugins.registry import PluginRegistry
from app.services.business_plugin_service import BusinessPluginService
from tests.unit.plugins.conftest import manifest_toml
from tests.unit.plugins.fakes import FakeActivityLog

PLUGIN_KEY = "shop"
PLUGIN_VERSION = "1.0.0"


class FakeBusinessPluginRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, UUID], BusinessPlugin] = {}
        self.race_winner: BusinessPlugin | None = None
        self.insert_error: IntegrityError | None = None
        self.locked_reads = 0
        self.inserts = 0
        self.rollbacks = 0

    def get(self, business_id: UUID, plugin_id: UUID) -> BusinessPlugin | None:
        return self.rows.get((business_id, plugin_id))

    def get_for_update(self, business_id: UUID, plugin_id: UUID) -> BusinessPlugin | None:
        self.locked_reads += 1
        return self.rows.get((business_id, plugin_id))

    def add_if_absent(self, business_plugin: BusinessPlugin) -> BusinessPlugin | None:
        self.inserts += 1
        if self.insert_error is not None:
            raise self.insert_error
        key = (business_plugin.business_id, business_plugin.plugin_id)
        if self.race_winner is not None:
            self.rows[key] = self.race_winner
            return None
        business_plugin.id = uuid4()
        self.rows[key] = business_plugin
        return business_plugin

    def save(self, business_plugin: BusinessPlugin) -> BusinessPlugin:
        return business_plugin

    def rollback(self) -> None:
        self.rollbacks += 1


class FakePlugins:
    def __init__(self, plugin: Plugin) -> None:
        self._plugin = plugin

    def get_by_key(self, key: str) -> Plugin | None:
        return self._plugin if key == self._plugin.key else None


def _user(*permissions: str, slug: str = RoleSlug.INDIVIDUAL_USER) -> User:
    role = Role(slug=slug, name=slug, permissions=[Permission(name=name) for name in permissions])
    return User(id=uuid4(), roles=[role])


def _provider() -> User:
    return _user(PermissionName.BUSINESS_CREATE, slug=RoleSlug.BUSINESS_SERVICE_PROVIDER)


def _admin() -> User:
    return _user(PermissionName.BUSINESS_UPDATE_ANY, PermissionName.BUSINESS_VIEW_ANY)


def _registry(version: str = PLUGIN_VERSION) -> PluginRegistry:
    manifest = parse_manifest(manifest_toml(PLUGIN_KEY, version=version).encode())
    loaded = LoadedPlugin(
        manifest=manifest,
        root=Path(PLUGIN_KEY),
        content_sha256="0" * 64,
        routers=(),
        model_bases=(),
    )
    return PluginRegistry(plugins=(loaded,))


class Scenario:
    def __init__(self, owner: User, *, compatible: bool = True) -> None:
        self.owner = owner
        self.business = Business(
            id=uuid4(),
            owner_id=owner.id,
            name="Shop",
            status=BusinessStatus.ACTIVE,
            category_id=uuid4(),
        )
        self.plugin = Plugin(
            id=uuid4(),
            key=PLUGIN_KEY,
            name="Shop",
            version=PLUGIN_VERSION,
            status=PluginStatus.ENABLED,
            business_type=PluginBusinessType.PRODUCT,
        )
        self.repository = FakeBusinessPluginRepository()
        self.activity = FakeActivityLog()
        self.service = BusinessPluginService(db=None)  # type: ignore[arg-type]
        overrides: dict[str, Any] = {
            "_business_plugins": self.repository,
            "_plugins": FakePlugins(self.plugin),
            "_activity_logs": self.activity,
            "_category_chain": lambda _business: [],
            "_compatible_plugins": lambda _chain: (
                {self.plugin.id: self.plugin} if compatible else {}
            ),
        }
        for name, value in overrides.items():
            setattr(self.service, name, value)
        self.service._businesses.get = self._get_business  # type: ignore[method-assign]

    def _get_business(self, business_id: UUID) -> Business:
        if business_id != self.business.id:
            raise NotFoundError(BusinessMessages.NOT_FOUND)
        return self.business

    def enable(self, actor: User, registry: PluginRegistry | None = None) -> BusinessPlugin:
        _, row = self.service.enable(self.business.id, PLUGIN_KEY, actor, registry or _registry())
        return row

    def disable(self, actor: User) -> BusinessPlugin | None:
        _, row = self.service.disable(self.business.id, PLUGIN_KEY, actor)
        return row

    def add_row(self, status: BusinessPluginStatus) -> BusinessPlugin:
        row = BusinessPlugin(
            id=uuid4(),
            business_id=self.business.id,
            plugin_id=self.plugin.id,
            status=status,
            enabled_by=self.owner.id,
        )
        self.repository.rows[(self.business.id, self.plugin.id)] = row
        return row

    def actions(self) -> list[str]:
        return [entry["action"] for entry in self.activity.entries]


def test_verified_owner_enables_once_and_logs_once() -> None:
    scenario = Scenario(_provider())
    row = scenario.enable(scenario.owner)
    assert row.status == BusinessPluginStatus.ACTIVE
    assert row.enabled_by == scenario.owner.id
    assert scenario.enable(scenario.owner) is row
    assert scenario.repository.inserts == 1
    assert scenario.actions() == [ActivityAction.BUSINESS_PLUGIN_ENABLED]
    assert scenario.activity.entries[0]["actor"] is scenario.owner


def test_losing_the_concurrent_insert_race_returns_the_winning_row_without_a_log() -> None:
    scenario = Scenario(_provider())
    winner = BusinessPlugin(
        id=uuid4(),
        business_id=scenario.business.id,
        plugin_id=scenario.plugin.id,
        status=BusinessPluginStatus.ACTIVE,
        enabled_by=scenario.owner.id,
    )
    scenario.repository.race_winner = winner
    assert scenario.enable(scenario.owner) is winner
    assert scenario.repository.locked_reads == 2
    assert scenario.actions() == []


def test_losing_the_race_to_a_disabled_row_reactivates_it_and_logs_once() -> None:
    scenario = Scenario(_provider())
    scenario.repository.race_winner = BusinessPlugin(
        id=uuid4(),
        business_id=scenario.business.id,
        plugin_id=scenario.plugin.id,
        status=BusinessPluginStatus.DISABLED,
        enabled_by=None,
    )
    row = scenario.enable(scenario.owner)
    assert row.status == BusinessPluginStatus.ACTIVE
    assert scenario.actions() == [ActivityAction.BUSINESS_PLUGIN_ENABLED]


def test_disabled_row_is_reactivated_with_a_locked_read() -> None:
    scenario = Scenario(_provider())
    existing = scenario.add_row(BusinessPluginStatus.DISABLED)
    assert scenario.enable(scenario.owner) is existing
    assert existing.status == BusinessPluginStatus.ACTIVE
    assert scenario.repository.inserts == 0
    assert scenario.repository.locked_reads == 1


def test_disable_is_idempotent_and_logs_only_the_change() -> None:
    scenario = Scenario(_provider())
    assert scenario.disable(scenario.owner) is None
    scenario.add_row(BusinessPluginStatus.ACTIVE)
    assert scenario.disable(scenario.owner).status == BusinessPluginStatus.DISABLED  # type: ignore[union-attr]
    scenario.disable(scenario.owner)
    assert scenario.actions() == [ActivityAction.BUSINESS_PLUGIN_DISABLED]


@pytest.mark.parametrize("operation", ["enable", "disable"])
def test_other_users_cannot_change_a_business(operation: str) -> None:
    scenario = Scenario(_provider())
    scenario.add_row(BusinessPluginStatus.ACTIVE)
    for stranger in (_provider(), _user(), _user(PermissionName.BUSINESS_VIEW_ANY)):
        with pytest.raises(AuthorizationError) as error:
            getattr(scenario, operation)(stranger)
        assert error.value.message == BusinessMessages.NOT_OWNER
    assert scenario.actions() == []


def test_owner_without_an_approved_provider_role_cannot_enable() -> None:
    scenario = Scenario(_user())
    with pytest.raises(AuthorizationError) as error:
        scenario.enable(scenario.owner)
    assert error.value.message == BusinessPluginMessages.ROLE_NOT_VERIFIED
    assert scenario.repository.inserts == 0


def test_owner_without_an_approved_provider_role_can_still_disable() -> None:
    scenario = Scenario(_user())
    scenario.add_row(BusinessPluginStatus.ACTIVE)
    assert scenario.disable(scenario.owner).status == BusinessPluginStatus.DISABLED  # type: ignore[union-attr]


def test_admin_with_update_any_can_manage_any_business() -> None:
    scenario = Scenario(_provider())
    admin = _admin()
    assert scenario.enable(admin).enabled_by == admin.id
    assert scenario.disable(admin).status == BusinessPluginStatus.DISABLED  # type: ignore[union-attr]
    assert [entry["actor"] for entry in scenario.activity.entries] == [admin, admin]


def test_inactive_business_and_incompatible_or_unloaded_plugin_are_refused() -> None:
    inactive = Scenario(_provider())
    inactive.business.status = BusinessStatus.INACTIVE
    with pytest.raises(BusinessRuleError, match=BusinessMessages.INACTIVE):
        inactive.enable(inactive.owner)
    incompatible = Scenario(_provider(), compatible=False)
    with pytest.raises(BusinessRuleError, match=BusinessPluginMessages.INCOMPATIBLE):
        incompatible.enable(incompatible.owner)
    stale = Scenario(_provider())
    with pytest.raises(NotFoundError):
        stale.enable(stale.owner, _registry(version="2.0.0"))
    for scenario in (inactive, incompatible, stale):
        assert scenario.repository.inserts == 0
        assert scenario.actions() == []


def test_access_requires_owner_or_view_any_and_an_active_association() -> None:
    scenario = Scenario(_provider())
    authorize = scenario.service.authorize_access
    with pytest.raises(AuthorizationError, match=BusinessPluginMessages.NOT_ENABLED_FOR_BUSINESS):
        authorize(scenario.business.id, PLUGIN_KEY, scenario.owner)
    scenario.add_row(BusinessPluginStatus.ACTIVE)
    assert authorize(scenario.business.id, PLUGIN_KEY, scenario.owner) is scenario.business
    assert authorize(scenario.business.id, PLUGIN_KEY, _admin()) is scenario.business
    with pytest.raises(AuthorizationError, match=BusinessMessages.NOT_OWNER):
        authorize(scenario.business.id, PLUGIN_KEY, _provider())


def test_access_is_refused_for_unverified_owners_inactive_businesses_and_disabled_plugins() -> None:
    unverified = Scenario(_user())
    unverified.add_row(BusinessPluginStatus.ACTIVE)
    with pytest.raises(AuthorizationError, match=BusinessPluginMessages.ROLE_NOT_VERIFIED):
        unverified.service.authorize_access(unverified.business.id, PLUGIN_KEY, unverified.owner)
    inactive = Scenario(_provider())
    inactive.add_row(BusinessPluginStatus.ACTIVE)
    inactive.business.status = BusinessStatus.INACTIVE
    with pytest.raises(BusinessRuleError, match=BusinessMessages.INACTIVE):
        inactive.service.authorize_access(inactive.business.id, PLUGIN_KEY, inactive.owner)
    disabled = Scenario(_provider())
    disabled.add_row(BusinessPluginStatus.ACTIVE)
    disabled.plugin.status = PluginStatus.DISABLED
    with pytest.raises(NotFoundError):
        disabled.service.authorize_access(disabled.business.id, PLUGIN_KEY, disabled.owner)
    association_disabled = Scenario(_provider())
    association_disabled.add_row(BusinessPluginStatus.DISABLED)
    with pytest.raises(AuthorizationError, match=BusinessPluginMessages.NOT_ENABLED_FOR_BUSINESS):
        association_disabled.service.authorize_access(
            association_disabled.business.id, PLUGIN_KEY, association_disabled.owner
        )


def test_access_to_another_plugins_key_is_refused() -> None:
    scenario = Scenario(_provider())
    scenario.add_row(BusinessPluginStatus.ACTIVE)
    with pytest.raises(NotFoundError):
        scenario.service.authorize_access(scenario.business.id, "other", scenario.owner)


def _insert_failure(violation: type[psycopg.errors.IntegrityError]) -> IntegrityError:
    return IntegrityError("INSERT INTO business_plugins", {}, violation("constraint violated"))


def test_foreign_key_violation_during_enable_is_a_conflict_without_an_audit_entry() -> None:
    scenario = Scenario(_provider())
    failure = _insert_failure(psycopg.errors.ForeignKeyViolation)
    scenario.repository.insert_error = failure
    with pytest.raises(ConflictError) as error:
        scenario.enable(scenario.owner)
    assert error.value.message == BusinessPluginMessages.ENABLE_TARGET_REMOVED
    assert error.value.status_code == 409
    assert error.value.__cause__ is failure
    assert scenario.repository.rollbacks == 1
    assert scenario.repository.rows == {}
    assert scenario.actions() == []


@pytest.mark.parametrize(
    "violation",
    [
        psycopg.errors.NotNullViolation,
        psycopg.errors.UniqueViolation,
        psycopg.errors.CheckViolation,
        psycopg.errors.ExclusionViolation,
    ],
)
def test_other_integrity_violations_during_enable_are_not_mislabelled_as_conflicts(
    violation: type[psycopg.errors.IntegrityError],
) -> None:
    scenario = Scenario(_provider())
    failure = _insert_failure(violation)
    scenario.repository.insert_error = failure
    with pytest.raises(IntegrityError) as error:
        scenario.enable(scenario.owner)
    assert error.value is failure
    assert scenario.repository.rollbacks == 1
    assert scenario.repository.rows == {}
    assert scenario.actions() == []


def test_integrity_errors_without_a_sqlstate_are_not_treated_as_foreign_key_violations() -> None:
    scenario = Scenario(_provider())
    scenario.repository.insert_error = IntegrityError(
        "INSERT INTO business_plugins", {}, Exception("unknown driver error")
    )
    with pytest.raises(IntegrityError):
        scenario.enable(scenario.owner)
    assert scenario.repository.rollbacks == 1
    assert scenario.actions() == []
