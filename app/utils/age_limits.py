from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OpSetting


DEFAULT_MIN_AGE = 16
DEFAULT_MAX_AGE = 99
ABSOLUTE_MIN_AGE = 1
ABSOLUTE_MAX_AGE = 99


def normalize_age_limits(
    min_age: int,
    max_age: int,
) -> tuple[int, int]:
    if (
        min_age < ABSOLUTE_MIN_AGE
        or max_age > ABSOLUTE_MAX_AGE
        or min_age >= max_age
    ):
        return DEFAULT_MIN_AGE, DEFAULT_MAX_AGE

    return min_age, max_age


async def get_age_limits(session: AsyncSession) -> tuple[int, int]:
    settings = await session.get(OpSetting, 1)
    if settings is None:
        settings = OpSetting(
            id=1,
            min_age=DEFAULT_MIN_AGE,
            max_age=DEFAULT_MAX_AGE,
        )
        session.add(settings)
        await session.commit()

    return normalize_age_limits(settings.min_age, settings.max_age)
