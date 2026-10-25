from aiosqlite import Connection
from arclet.entari import Plugin
from sqlalchemy import AdaptedConnection, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool.base import _ConnectionRecord

PLUGIN = Plugin.current()


@event.listens_for(Engine, "connect")
def on_connect(
    connection: AdaptedConnection,
    connection_record: _ConnectionRecord,
) -> None:
    if not isinstance(connection.driver_connection, Connection):
        return

    async def set_sqlite_pragma(connection: Connection) -> None:
        async with connection.cursor() as cursor:
            await cursor.execute("PRAGMA foreign_keys = ON")
            await cursor.execute("PRAGMA journal_mode = WAL")
            await cursor.execute("PRAGMA synchronous = NORMAL")
            await cursor.execute("PRAGMA temp_store = MEMORY")

    connection.run_async(set_sqlite_pragma)


@PLUGIN.collect
def unregister() -> None:
    event.remove(Engine, "connect", on_connect)
