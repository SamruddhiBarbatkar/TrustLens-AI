from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def request_validation_exception_handler(
    _request: Request, _exception: RequestValidationError
) -> JSONResponse:
    """Return a stable public validation response without internal detail."""
    return JSONResponse(status_code=422, content={"detail": "Request validation failed."})


async def unhandled_exception_handler(_request: Request, _exception: Exception) -> JSONResponse:
    """Prevent unexpected implementation details and stack traces reaching clients."""
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})
