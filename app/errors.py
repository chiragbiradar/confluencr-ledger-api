from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def _error_body(code: str, message: str, details: dict = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _field_code(loc: list) -> str:
    field = loc[-1] if loc else ""
    if field == "type":
        return "INVALID_TRANSACTION_TYPE"
    if field == "amount":
        return "INVALID_AMOUNT"
    if field in ("page", "limit"):
        return "INVALID_PAGINATION"
    return "VALIDATION_ERROR"


def _field_status(code: str) -> int:
    if code == "INVALID_PAGINATION":
        return 400
    return 422


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=_error_body(exc.code, exc.message, exc.details))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = list(first.get("loc", []))
    # strip "body" / "query" prefix
    loc = [l for l in loc if l not in ("body", "query")]
    code = _field_code(loc)
    status = _field_status(code)
    message = first.get("msg", "Validation error")
    fields = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in errors]
    return JSONResponse(status_code=status, content=_error_body(code, message, {"fields": fields}))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code, content=_error_body(code, str(exc.detail)))


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected error")
    return JSONResponse(status_code=500, content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"))
