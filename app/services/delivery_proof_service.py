from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import DeliveryRequestMessages, OrderMessages
from app.models.delivery_request import DeliveryRequest
from app.models.user import User
from app.repositories.delivery_request_repository import DeliveryRequestRepository
from app.repositories.order_repository import OrderRepository


class DeliveryProofService:
    def __init__(self, db: Session) -> None:
        self._requests = DeliveryRequestRepository(db)
        self._orders = OrderRepository(db)

    def path_for_customer(self, order_id: UUID, actor: User) -> str:
        order = self._orders.get(order_id)
        if order is None or order.customer_id != actor.id:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return self._proof_path(self._requests.latest_for_order(order.id))

    def path_for_courier(self, request_id: UUID, actor: User) -> str:
        return self._proof_path(self._requests.get_for_courier(request_id, actor.id))

    def path_for_promoter(self, request_id: UUID, actor: User) -> str:
        request = self._requests.get(request_id)
        if request is not None and request.promoter_id != actor.id:
            request = None
        return self._proof_path(request)

    def _proof_path(self, request: DeliveryRequest | None) -> str:
        if request is None or request.proof_image_path is None:
            raise NotFoundError(DeliveryRequestMessages.PROOF_NOT_FOUND)
        if not Path(request.proof_image_path).is_file():
            raise NotFoundError(DeliveryRequestMessages.PROOF_NOT_FOUND)
        return request.proof_image_path
