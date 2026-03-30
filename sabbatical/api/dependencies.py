import databases
from fastapi import Request

from sabbatical.core.config import SabbaticalConfig


async def get_db(request: Request) -> databases.Database:
    return request.app.state.db


async def get_config(request: Request) -> SabbaticalConfig:
    return request.app.state.config


async def get_dispatcher(request: Request):
    return request.app.state.dispatcher


async def get_broadcaster(request: Request):
    return request.app.state.broadcaster
