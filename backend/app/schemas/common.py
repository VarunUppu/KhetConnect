# File: backend/app/schemas/common.py
from pydantic import BaseModel

# India-only for now (+91, mobile numbers start with 6-9).
# The DB constraint is looser (generic E.164) so this can be widened later.
PHONE_PATTERN = r"^\+91[6-9][0-9]{9}$"


class ErrorResponse(BaseModel):
    detail: str


class MessageResponse(BaseModel):
    message: str