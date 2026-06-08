import logging
import shutil
from pathlib import Path
from sqlalchemy import inspect
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from app.utils.config import DB
from app.database.models import Base
from app.utils.age_limits import DEFAULT_MAX_AGE, DEFAULT_MIN_AGE
from app.utils.reveal_sender import DEFAULT_REVEAL_SENDER_PRICE


logger = logging.getLogger('database.engine')


def _apply_runtime_migrations(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())

    if 'op_settings' in table_names:
        columns = {
            column['name']
            for column in inspector.get_columns('op_settings')
        }
        if 'min_age' not in columns:
            sync_conn.exec_driver_sql(
                'ALTER TABLE op_settings '
                'ADD COLUMN min_age INTEGER NOT NULL DEFAULT %i'
                % DEFAULT_MIN_AGE
            )
        if 'max_age' not in columns:
            sync_conn.exec_driver_sql(
                'ALTER TABLE op_settings '
                'ADD COLUMN max_age INTEGER NOT NULL DEFAULT %i'
                % DEFAULT_MAX_AGE
            )

    if 'price_settings' in table_names:
        columns = {
            column['name']
            for column in inspector.get_columns('price_settings')
        }
        if 'reveal_sender_price' not in columns:
            sync_conn.exec_driver_sql(
                'ALTER TABLE price_settings '
                'ADD COLUMN reveal_sender_price INTEGER NOT NULL DEFAULT %i'
                % DEFAULT_REVEAL_SENDER_PRICE
            )


def _resolve_db_url(database: DB) -> str:
    db_url = (database.url or '').strip()
    if not db_url:
        return str(
            URL(
                'postgresql+asyncpg',
                database.user,
                database.password,
                database.host,
                database.port,
                database.name,
                query={},
            )
        )

    url = make_url(db_url)
    if url.get_backend_name() != 'sqlite' or not url.database:
        return db_url

    db_path = Path(url.database)
    if db_path.is_absolute():
        return db_url

    cwd = Path.cwd()

    if not (cwd / db_path).exists():
        for p in sorted(cwd.glob('*.sqlite3')):
            logger.warning('DB %s not found, falling back to %s', db_path, p.name)
            url = url.set(database=str(p))
            break

    db_path = Path(url.database)
    shared_candidates = [
        cwd / 'shared',
        cwd.parent / 'shared',
        cwd.parent.parent / 'shared',
    ]
    shared_dir = next(
        (candidate for candidate in shared_candidates if candidate.is_dir()),
        None,
    )

    if shared_dir is None:
        return db_url

    local_db = cwd / db_path
    shared_db = shared_dir / db_path.name

    if not shared_db.exists() and local_db.exists():
        shared_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_db, shared_db)
        logger.info('Moved sqlite database to shared dir: %s', shared_db)

    return str(url.set(database=str(shared_db)))


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_runtime_migrations)
        logger.info('Tables created successfully')


async def create_sessionmaker(database: DB) -> async_sessionmaker:
    db_url = _resolve_db_url(database)
    engine = create_async_engine(db_url, future=True)
    logger.info('Connected to database via %s', db_url.split(':', 1)[0])

    await create_tables(engine)
    return async_sessionmaker(engine, expire_on_commit=False)
