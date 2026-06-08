from aiogram.filters import Filter


class NotSubbed(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(
        self,
        _,
        required_sponsors: list | None = None,
        sponsors: list | None = None,
    ) -> bool:
        if required_sponsors is not None:
            return bool(required_sponsors)
        return bool(sponsors or [])
