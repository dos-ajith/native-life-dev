from collections.abc import Callable

from app.ai.tools.deal_tools import DealCategoryReferenceRead
from app.core.messages import AIMessages
from app.models.ai_draft import AIDraftKind
from app.models.order import DeliveryOption
from app.schemas.ai import AIInputKind, AINextStepRead, AIOptionRead
from app.schemas.ai_deal_draft import MISSING_PICKUP_OR_DELIVERY

CATEGORY_FIELD = "category_id"
DELIVERY_OPTIONS_FIELD = "delivery_options"
PICKUP_FIELD = "pickup_location"

STEP_ORDER = (
    "name",
    CATEGORY_FIELD,
    "items",
    "starts_at",
    "valid_until",
    DELIVERY_OPTIONS_FIELD,
    PICKUP_FIELD,
)
STEP_FIELD_FOR_MISSING = {MISSING_PICKUP_OR_DELIVERY: PICKUP_FIELD}
DATETIME_FIELDS = frozenset({"starts_at", "valid_until"})

DELIVERY_OPTION_LABELS = {
    DeliveryOption.SELF_PICKUP: AIMessages.DEAL_OPTION_SELF_PICKUP,
    DeliveryOption.INSTANT: AIMessages.DEAL_OPTION_INSTANT,
    DeliveryOption.ROUTE: AIMessages.DEAL_OPTION_ROUTE,
}

STEP_QUESTIONS = {
    "name": AIMessages.DEAL_QUESTION_NAME,
    CATEGORY_FIELD: AIMessages.DEAL_QUESTION_CATEGORY,
    "items": AIMessages.DEAL_QUESTION_ITEMS,
    "starts_at": AIMessages.DEAL_QUESTION_STARTS_AT,
    "valid_until": AIMessages.DEAL_QUESTION_VALID_UNTIL,
    DELIVERY_OPTIONS_FIELD: AIMessages.DEAL_QUESTION_DELIVERY,
    PICKUP_FIELD: AIMessages.DEAL_QUESTION_PICKUP,
}

CONFIRM_OPTIONS = (
    ("confirm", AIMessages.DEAL_OPTION_CONFIRM),
    ("cancel", AIMessages.DEAL_OPTION_CANCEL),
    ("change", AIMessages.DEAL_OPTION_CHANGE),
)


def _step(
    field: str | None, input_kind: AIInputKind, options: list[AIOptionRead] | None = None
) -> AINextStepRead:
    return AINextStepRead(
        flow=AIDraftKind.DEAL, field=field, input=input_kind, options=options or []
    )


def step_question(step: AINextStepRead) -> str:
    if step.field is None:
        return AIMessages.DEAL_QUESTION_CONFIRM
    return STEP_QUESTIONS[step.field]


def next_step_field(missing: list[str]) -> str | None:
    fields = {STEP_FIELD_FOR_MISSING.get(name, name) for name in missing}
    return next((field for field in STEP_ORDER if field in fields), None)


def next_deal_step(
    missing: list[str], load_categories: Callable[[], list[DealCategoryReferenceRead]]
) -> AINextStepRead:
    field = next_step_field(missing)
    if field is None:
        return _step(
            None,
            AIInputKind.CONFIRM,
            [AIOptionRead(id=key, label=label, prompt=label) for key, label in CONFIRM_OPTIONS],
        )
    if field == CATEGORY_FIELD:
        return _step(
            field,
            AIInputKind.CHOICE,
            [
                AIOptionRead(
                    id=str(category.id),
                    label=category.name,
                    prompt=AIMessages.DEAL_OPTION_CATEGORY_PROMPT.format(name=category.name),
                )
                for category in load_categories()
            ],
        )
    if field == DELIVERY_OPTIONS_FIELD:
        return _step(
            field,
            AIInputKind.CHOICE,
            [
                AIOptionRead(id=option.value, label=label, prompt=label)
                for option, label in DELIVERY_OPTION_LABELS.items()
            ],
        )
    return _step(field, AIInputKind.DATETIME if field in DATETIME_FIELDS else AIInputKind.TEXT)
