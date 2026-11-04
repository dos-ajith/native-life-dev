from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.aadhaar_documents import routes as aadhaar_document_routes
from app.api.v1.account_roles import routes as account_role_routes
from app.api.v1.admin import geography as admin_geography_routes
from app.api.v1.admin import routes as admin_routes
from app.api.v1.ai import routes as ai_routes
from app.api.v1.auth import google_routes as google_auth_routes
from app.api.v1.auth import phone_routes as phone_auth_routes
from app.api.v1.auth import routes as auth_routes
from app.api.v1.business_plugins import routes as business_plugin_routes
from app.api.v1.businesses import admin_routes as business_admin_routes
from app.api.v1.businesses import documents as business_document_routes
from app.api.v1.businesses import images as business_image_routes
from app.api.v1.businesses import routes as business_routes
from app.api.v1.categories import admin_routes as category_admin_routes
from app.api.v1.categories import routes as category_routes
from app.api.v1.chats import routes as chat_routes
from app.api.v1.collections import routes as collection_routes
from app.api.v1.communities import admin_routes as community_admin_routes
from app.api.v1.communities import chat as community_chat_routes
from app.api.v1.communities import polls as community_poll_routes
from app.api.v1.communities import routes as community_routes
from app.api.v1.communities import timeline as community_timeline_routes
from app.api.v1.deals import acceptance as deal_acceptance_routes
from app.api.v1.deals import delivery as deal_delivery_routes
from app.api.v1.deals import explore as deal_explore_routes
from app.api.v1.deals import images as deal_image_routes
from app.api.v1.deals import items as deal_item_routes
from app.api.v1.deals import orders as deal_order_routes
from app.api.v1.deals import participation as deal_participation_routes
from app.api.v1.deals import routes as deal_routes
from app.api.v1.deliveries import customer as delivery_customer_routes
from app.api.v1.deliveries import requests as delivery_request_routes
from app.api.v1.deliveries import routes as delivery_route_routes
from app.api.v1.deliveries import tracking as delivery_tracking_routes
from app.api.v1.deliveries import vehicles as delivery_vehicle_routes
from app.api.v1.events import images as event_image_routes
from app.api.v1.events import routes as event_routes
from app.api.v1.explore import routes as explore_routes
from app.api.v1.geography import routes as geography_routes
from app.api.v1.lost_found import images as lost_found_image_routes
from app.api.v1.lost_found import routes as lost_found_routes
from app.api.v1.native_places import admin_place_routes as native_place_profile_admin_routes
from app.api.v1.native_places import admin_routes as native_place_admin_routes
from app.api.v1.native_places import me_routes as user_native_place_routes
from app.api.v1.native_places import routes as native_place_routes
from app.api.v1.notifications import devices as device_routes
from app.api.v1.notifications import routes as notification_routes
from app.api.v1.orders import business as order_business_routes
from app.api.v1.orders import cart as cart_routes
from app.api.v1.orders import routes as order_routes
from app.api.v1.orders import seller as order_seller_routes
from app.api.v1.pages import mobile as mobile_page_routes
from app.api.v1.pages import routes as page_routes
from app.api.v1.permissions import routes as permission_routes
from app.api.v1.plugins import admin_routes as plugin_admin_routes
from app.api.v1.popular_places import admin_routes as popular_place_admin_routes
from app.api.v1.popular_places import routes as popular_place_routes
from app.api.v1.posts import admin_routes as post_admin_routes
from app.api.v1.posts import comments as post_comment_routes
from app.api.v1.posts import likes as post_like_routes
from app.api.v1.posts import routes as post_routes
from app.api.v1.posts import saves as post_save_routes
from app.api.v1.posts import shares as post_share_routes
from app.api.v1.realtime import routes as realtime_routes
from app.api.v1.role_upgrade_requests import admin_routes as role_upgrade_request_admin_routes
from app.api.v1.role_upgrade_requests import routes as role_upgrade_request_routes
from app.api.v1.roles import routes as role_routes
from app.api.v1.settings import routes as setting_routes
from app.api.v1.updates import routes as update_routes
from app.api.v1.user_settings import routes as user_settings_routes
from app.api.v1.users import addresses as user_address_routes
from app.api.v1.users import blocks as user_block_routes
from app.api.v1.users import follows as user_follow_routes
from app.api.v1.users import routes as user_routes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ai_routes.router)
api_router.include_router(auth_routes.router)
api_router.include_router(phone_auth_routes.router)
api_router.include_router(google_auth_routes.router)
api_router.include_router(admin_routes.router)
api_router.include_router(admin_geography_routes.router)
api_router.include_router(geography_routes.router)
api_router.include_router(role_routes.router)
api_router.include_router(role_upgrade_request_routes.router)
api_router.include_router(role_upgrade_request_admin_routes.router)
api_router.include_router(account_role_routes.router)
api_router.include_router(account_role_routes.me_router)
api_router.include_router(permission_routes.router)
api_router.include_router(setting_routes.router)
api_router.include_router(user_settings_routes.router)
api_router.include_router(user_routes.router)
api_router.include_router(user_address_routes.router)
api_router.include_router(aadhaar_document_routes.router)
api_router.include_router(user_follow_routes.router)
api_router.include_router(user_follow_routes.me_router)
api_router.include_router(user_block_routes.router)
api_router.include_router(user_block_routes.me_router)
api_router.include_router(chat_routes.router)
api_router.include_router(notification_routes.router)
api_router.include_router(device_routes.router)
api_router.include_router(realtime_routes.router)
api_router.include_router(page_routes.router)
api_router.include_router(mobile_page_routes.router)
api_router.include_router(update_routes.router)
api_router.include_router(post_routes.router)
api_router.include_router(event_routes.router)
api_router.include_router(event_image_routes.router)
api_router.include_router(explore_routes.router)
api_router.include_router(lost_found_routes.router)
api_router.include_router(lost_found_image_routes.router)
api_router.include_router(post_comment_routes.router)
api_router.include_router(post_like_routes.router)
api_router.include_router(post_save_routes.router)
api_router.include_router(post_save_routes.me_router)
api_router.include_router(post_share_routes.router)
api_router.include_router(collection_routes.me_router)
api_router.include_router(business_routes.router)
api_router.include_router(business_routes.me_router)
api_router.include_router(business_admin_routes.router)
api_router.include_router(business_document_routes.router)
api_router.include_router(business_image_routes.router)
api_router.include_router(business_plugin_routes.router)
api_router.include_router(category_routes.router)
api_router.include_router(category_admin_routes.router)
api_router.include_router(popular_place_routes.router)
api_router.include_router(native_place_routes.router)
api_router.include_router(user_native_place_routes.router)
api_router.include_router(native_place_admin_routes.router)
api_router.include_router(native_place_profile_admin_routes.router)
api_router.include_router(popular_place_admin_routes.router)
api_router.include_router(post_admin_routes.router)
api_router.include_router(community_routes.router)
api_router.include_router(community_admin_routes.router)
api_router.include_router(community_chat_routes.router)
api_router.include_router(community_poll_routes.router)
api_router.include_router(community_timeline_routes.router)
api_router.include_router(deal_explore_routes.router)
api_router.include_router(deal_routes.router)
api_router.include_router(deal_routes.me_router)
api_router.include_router(deal_item_routes.router)
api_router.include_router(deal_image_routes.router)
api_router.include_router(deal_acceptance_routes.router)
api_router.include_router(deal_acceptance_routes.me_router)
api_router.include_router(deal_delivery_routes.router)
api_router.include_router(delivery_vehicle_routes.router)
api_router.include_router(delivery_route_routes.router)
api_router.include_router(delivery_request_routes.router)
api_router.include_router(delivery_tracking_routes.router)
api_router.include_router(delivery_customer_routes.router)
api_router.include_router(deal_delivery_routes.settings_router)
api_router.include_router(deal_participation_routes.router)
api_router.include_router(deal_participation_routes.me_router)
api_router.include_router(deal_order_routes.router)
api_router.include_router(cart_routes.router)
api_router.include_router(order_routes.router)
api_router.include_router(order_routes.business_router)
api_router.include_router(order_business_routes.router)
api_router.include_router(order_seller_routes.router)
api_router.include_router(plugin_admin_routes.router)
