class EcommerceAction:
    PRODUCT_CREATED = "ecommerce.product.created"
    PRODUCT_UPDATED = "ecommerce.product.updated"
    PRODUCT_ACTIVATED = "ecommerce.product.activated"
    PRODUCT_DEACTIVATED = "ecommerce.product.deactivated"
    PRODUCT_IMAGE_ADDED = "ecommerce.product.image_added"
    PRODUCT_IMAGE_REMOVED = "ecommerce.product.image_removed"
    CATEGORY_CREATED = "ecommerce.category.created"
    STOCK_ADJUSTED = "ecommerce.stock.adjusted"
    LOW_STOCK_THRESHOLD_UPDATED = "ecommerce.stock.threshold_updated"
    SETTINGS_UPDATED = "ecommerce.settings.updated"


class EcommerceEntity:
    PRODUCT = "ecommerce_product"
    PRODUCT_CATEGORY = "ecommerce_product_category"
    STOCK = "ecommerce_stock"
    SETTINGS = "ecommerce_settings"
