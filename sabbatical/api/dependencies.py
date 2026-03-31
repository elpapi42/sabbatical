from fastapi import Request

from sabbatical.core.config import SabbaticalConfig
from sabbatical.core.context import Database


async def get_db(request: Request) -> Database:
    return request.app.state.db


async def get_config(request: Request) -> SabbaticalConfig:
    return request.app.state.config
