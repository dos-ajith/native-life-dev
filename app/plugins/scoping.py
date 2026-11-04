from dataclasses import dataclass

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

BUSINESS_ID_PARAMETER = "business_id"
NON_PATH_PARAMETER_LOCATIONS = {
    "query": "query_params",
    "header": "header_params",
    "cookie": "cookie_params",
    "body": "body_params",
}


@dataclass(frozen=True)
class BusinessScope:
    plugin_key: str


def is_business_scoped(route: APIRoute) -> bool:
    return BUSINESS_ID_PARAMETER in route.param_convertors


def business_scope_keys(dependant: Dependant) -> set[str]:
    keys = {dependant.call.plugin_key} if isinstance(dependant.call, BusinessScope) else set()
    for dependency in dependant.dependencies:
        keys |= business_scope_keys(dependency)
    return keys


def business_id_outside_path(dependant: Dependant) -> set[str]:
    locations = {
        location
        for location, attribute in NON_PATH_PARAMETER_LOCATIONS.items()
        if any(
            BUSINESS_ID_PARAMETER in (parameter.name, parameter.alias)
            for parameter in getattr(dependant, attribute)
        )
    }
    for dependency in dependant.dependencies:
        locations |= business_id_outside_path(dependency)
    return locations
