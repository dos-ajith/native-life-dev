from app.models.plugin import PluginBusinessType


class BusinessCategorySlug:
    ROOT = "business"
    PRODUCT = "business-product"
    SERVICE = "business-service"


class BusinessCategoryName:
    ROOT = "Business"
    PRODUCT = "Product"
    SERVICE = "Service"


BUSINESS_TYPE_ROOT_SLUGS = {
    PluginBusinessType.PRODUCT: BusinessCategorySlug.PRODUCT,
    PluginBusinessType.SERVICE: BusinessCategorySlug.SERVICE,
}
CORE_BUSINESS_CATEGORIES = (
    (BusinessCategorySlug.ROOT, BusinessCategoryName.ROOT, None),
    (BusinessCategorySlug.PRODUCT, BusinessCategoryName.PRODUCT, BusinessCategorySlug.ROOT),
    (BusinessCategorySlug.SERVICE, BusinessCategoryName.SERVICE, BusinessCategorySlug.ROOT),
)
