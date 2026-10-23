# File: backend/app/core/errors.py
from fastapi import HTTPException, status


def not_implemented(feature: str = "") -> HTTPException:
    detail = "Not implemented yet" + (f": {feature}" if feature else "")
    return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)