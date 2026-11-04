from typing import Annotated

from fastapi import Depends

from app.plugins.sdk import PluginBusiness, User, require_business_plugin, require_permission

from ..config import PLUGIN_KEY
from ..permissions import EcommercePermission

BusinessDep = Annotated[PluginBusiness, Depends(require_business_plugin(PLUGIN_KEY))]
ProductViewerDep = Annotated[User, Depends(require_permission(EcommercePermission.PRODUCTS_VIEW))]
ProductManagerDep = Annotated[
    User, Depends(require_permission(EcommercePermission.PRODUCTS_MANAGE))
]
InventoryViewerDep = Annotated[
    User, Depends(require_permission(EcommercePermission.INVENTORY_VIEW))
]
InventoryManagerDep = Annotated[
    User, Depends(require_permission(EcommercePermission.INVENTORY_MANAGE))
]
SettingsViewerDep = Annotated[User, Depends(require_permission(EcommercePermission.SETTINGS_VIEW))]
SettingsManagerDep = Annotated[
    User, Depends(require_permission(EcommercePermission.SETTINGS_MANAGE))
]
