import logging

from fastapi import FastAPI, Depends
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api import status, task, check

from .dependencies import validate_token
from .worker import spawn_worker, terminate_worker


async def bad_request(request, exc):
    if exc.detail:
        if isinstance(exc.detail, dict):
            return JSONResponse(content=exc.detail, status_code=exc.status_code)
        elif isinstance(exc.detail, str):
            return JSONResponse(content={"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(content={"detail": "Bad Request"}, status_code=exc.status_code)


exception_handlers = {
    400: bad_request
}

app = FastAPI(
    dependencies=[Depends(validate_token)],
    exception_handlers=exception_handlers
)

app.include_router(status.router)
app.include_router(task.router)
app.include_router(check.router)


@app.on_event("startup")
def startup_event():
    spawn_worker()


"""
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    # or logger.error(f'{exc}')
    logging.getLogger("test").error(request, exc_str)
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
"""
