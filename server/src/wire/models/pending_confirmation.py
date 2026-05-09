from pydantic import BaseModel


class PendingConfirmationPayload(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    confirm_label: str
    cancel_label: str
    target_label: str
