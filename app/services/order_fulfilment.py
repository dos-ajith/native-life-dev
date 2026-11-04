from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError
from app.core.messages import OrderMessages
from app.models.order import ORDER_TRANSITIONS, Order, OrderStatus
from app.models.user import User
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "order"


class OrderFulfilment:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._activity_logs = ActivityLogService(db)

    def change_status(self, order: Order, target: OrderStatus, actor: User) -> Order:
        if target == OrderStatus.CANCELLED:
            raise BusinessRuleError(OrderMessages.USE_CANCEL)
        current = order.status
        if target not in ORDER_TRANSITIONS[current]:
            raise BusinessRuleError(
                OrderMessages.TRANSITION_INVALID.format(current=current.value, target=target.value)
            )
        order.status = target
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ORDER_STATUS_CHANGED,
            entity_type=ENTITY_TYPE,
            entity_id=order.id,
            metadata={"from": current.value, "to": target.value},
        )
        return order
