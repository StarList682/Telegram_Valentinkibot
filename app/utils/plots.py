from io import BytesIO
from datetime import date, timedelta

import matplotlib
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio.session import AsyncSession

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.axes import Axes

from app.database.models import User, Bill


class BasePlotCreator(object):
    DAYS = 20
    WIDTH = 10

    LABEL_Y = 'Данные'

    TITLE_TEMPLATE = 'Статистика c %s по %s'

    @staticmethod
    def splitting(value: int) -> str:
        if value == 0:
            return ''

        if abs(value) < 1000:
            return str(int(value))

        return '%.1fk' % (value / 1000)

    @classmethod
    async def create_plot(cls, session: AsyncSession) -> BytesIO:
        today = date.today()

        data = (await cls.get_data(session, today))
        figure, _ = cls.configure_axes(data, today)

        figure.tight_layout()
        file = BytesIO()
        figure.savefig(file)
        file.seek(0)
        plt.close()

        return file

    @staticmethod
    async def get_day(session: AsyncSession, date: date) -> int:
        return 0

    @classmethod
    def get_offsets(cls, unix_time: date) -> list[date]:
        start_date = unix_time - timedelta(days=cls.DAYS - 1)
        for days in range(cls.DAYS):
            yield start_date + timedelta(days)

    @classmethod
    async def get_data(cls, session: AsyncSession, unix_time: float) -> list:
        return [
            await cls.get_day(session, offset)
            for offset in cls.get_offsets(unix_time)
        ]

    @classmethod
    def get_max_value(cls, data: list) -> int:
        max_value = max(data)

        if isinstance(max_value, tuple):
            max_value = max(max_value)

        return max(1, max_value)

    @classmethod
    def _create_row(
        cls,
        axes: Axes,
        data: list,
        color: str,
        max_value: int,
        offset: float = 0,
        width: float = 0.4,
        bottom: bool = False,
        splitting: bool = False,
    ) -> None:
        positions = [
            position + offset
            for position in
            range(len(data))
        ]

        axes.bar(
            positions,
            data,
            color=color,
            width=width,
            alpha=1,
        )

        for index, value in enumerate(data):
            axes.text(
                index + offset,
                (
                    value + (max_value * 0.02)
                    if not bottom else
                    -(max_value * 0.035)
                ),
                (
                    cls.splitting(value)
                    if splitting else
                    value if value else ''
                ),
                horizontalalignment='center',
                color=color,
                fontsize=(
                    10 if not bottom else 9
                ),
            )

    @classmethod
    def create_bars(cls, axes: Axes, data: list, max_value: int) -> None:
        cls._create_row(
            axes, data, '#645fd5', max_value, bottom=True,
        )

        axes.legend(
            handles=(
                mpatches.Patch(
                    color='#645fd5',
                    label='Число',
                ),
            )
        )

    @classmethod
    def configure_axes(cls, data: list, unix_time: float):
        date_labels = [
            offset.strftime("%d.%m")
            for offset in cls.get_offsets(unix_time)
        ]
        max_value = cls.get_max_value(data)

        figure, axes = plt.subplots(
            figsize=(cls.WIDTH, 6),
            facecolor='#f7fafc',
            dpi=110,
        )
        figure.patch.set_facecolor('#f7fafc')

        axes.set_xticks(
            range(len(data)),
            date_labels,
            fontsize=10,
            rotation=60,
            horizontalalignment='center',
        )
        axes.set_title(
            cls.TITLE_TEMPLATE % (
                date_labels[0],
                date_labels[-1],
            ),
            fontsize=16,
            fontweight='bold',
        )
        axes.set(
            ylabel=cls.LABEL_Y,
            facecolor='white',
        )
        axes.grid(axis='y', linestyle='--', alpha=0.2)
        axes.set_axisbelow(True)
        axes.set_ylim(0, max_value * 1.25)

        for spine in ('top', 'right'):
            axes.spines[spine].set_visible(False)
        axes.spines['left'].set_alpha(0.2)
        axes.spines['bottom'].set_alpha(0.2)

        cls.create_bars(axes, data, max_value)

        return figure, axes


class PaymentPlot(BasePlotCreator):
    LABEL_Y = 'Выручка, ₽'
    TITLE_TEMPLATE = 'Выручка и оплаты c %s по %s'

    @classmethod
    async def get_day(cls, session: AsyncSession, date: date) -> tuple[int, int]:
        revenue = await session.scalar(
            select(func.sum(Bill.amount))
            .where(
                Bill.date >= date,
                Bill.date < date + timedelta(1),
            )
        ) or 0
        payments_count = await session.scalar(
            select(func.count(Bill.id))
            .where(
                Bill.date >= date,
                Bill.date < date + timedelta(1),
            )
        ) or 0
        return revenue, payments_count

    @classmethod
    def configure_axes(cls, data: list, unix_time: float):
        date_labels = [
            offset.strftime("%d.%m")
            for offset in cls.get_offsets(unix_time)
        ]
        revenue = [item[0] for item in data]
        payments_count = [item[1] for item in data]
        max_revenue = max(1, max(revenue or [0]))
        max_payments = max(1, max(payments_count or [0]))
        positions = list(range(len(data)))

        figure, axes = plt.subplots(
            figsize=(cls.WIDTH, 6),
            facecolor='#f7fafc',
            dpi=110,
        )
        figure.patch.set_facecolor('#f7fafc')

        bars = axes.bar(
            positions,
            revenue,
            color='#2563eb',
            width=0.62,
            alpha=0.88,
        )
        axes.set_xticks(
            positions,
            date_labels,
            fontsize=10,
            rotation=60,
            horizontalalignment='center',
        )
        axes.set_title(
            cls.TITLE_TEMPLATE % (date_labels[0], date_labels[-1]),
            fontsize=16,
            fontweight='bold',
        )
        axes.set(
            ylabel=cls.LABEL_Y,
            facecolor='white',
        )
        axes.grid(axis='y', linestyle='--', alpha=0.2)
        axes.set_axisbelow(True)
        axes.set_ylim(0, max_revenue * 1.25)

        for spine in ('top', 'right'):
            axes.spines[spine].set_visible(False)
        axes.spines['left'].set_alpha(0.2)
        axes.spines['bottom'].set_alpha(0.2)

        for index, value in enumerate(revenue):
            if not value:
                continue
            axes.text(
                index,
                value + (max_revenue * 0.03),
                cls.splitting(value),
                horizontalalignment='center',
                color='#1d4ed8',
                fontsize=9,
                fontweight='bold',
            )

        second_axes = axes.twinx()
        line = second_axes.plot(
            positions,
            payments_count,
            color='#f97316',
            marker='o',
            linewidth=2,
            label='Оплаты',
        )[0]
        second_axes.set_ylabel('Количество оплат')
        second_axes.set_ylim(0, max_payments * 1.25)
        second_axes.spines['top'].set_visible(False)
        second_axes.spines['left'].set_visible(False)
        second_axes.spines['right'].set_alpha(0.2)

        for index, value in enumerate(payments_count):
            if not value:
                continue
            second_axes.text(
                index,
                value + (max_payments * 0.05),
                str(value),
                horizontalalignment='center',
                color='#ea580c',
                fontsize=9,
                fontweight='bold',
            )

        axes.legend(
            handles=[
                mpatches.Patch(
                    color='#2563eb',
                    label='Выручка',
                ),
                line,
            ],
        )
        return figure, axes


class UsersPlot(BasePlotCreator):
    LABEL_Y = 'Количество'
    TITLE_TEMPLATE = 'Рост, рефералы и баны c %s по %s'

    @classmethod
    async def get_day(
        cls,
        session: AsyncSession,
        date: date,
    ) -> tuple[int, int, int]:
        organic = await session.scalar(
            select(func.count(User.id))
            .where(
                User.join_date >= date,
                User.join_date < date + timedelta(1),
                User.ref == None,
                User.chat_only == False,
                User.id > 0,
            )
        ) or 0
        referral = await session.scalar(
            select(func.count(User.id))
            .where(
                User.join_date >= date,
                User.join_date < date + timedelta(1),
                User.ref != None,
                User.chat_only == False,
                User.id > 0,
            )
        ) or 0
        blocked = await session.scalar(
            select(func.count(User.id))
            .where(
                User.block_date >= date,
                User.block_date < date + timedelta(1),
                User.chat_only == False,
                User.id > 0,
            )
        ) or 0

        return (
            organic,
            referral,
            blocked,
        )

    @classmethod
    def get_max_value(cls, data: list) -> int:
        max_stack = max(
            ((item[0] + item[1]) for item in data),
            default=0,
        )
        max_blocked = max((item[2] for item in data), default=0)
        return max(1, max(max_stack, max_blocked))

    @classmethod
    def create_bars(cls, axes: Axes, data: list, max_value: int) -> None:
        organic = [
            item[0] for item in data
        ]
        referral = [
            item[1] for item in data
        ]
        blocked = [
            item[2] for item in data
        ]
        positions = list(range(len(data)))

        axes.bar(
            positions,
            organic,
            color='#2563eb',
            width=0.6,
            alpha=0.88,
        )
        axes.bar(
            positions,
            referral,
            bottom=organic,
            color='#10b981',
            width=0.6,
            alpha=0.88,
        )
        line = axes.plot(
            positions,
            blocked,
            color='#ef4444',
            marker='o',
            linewidth=2,
            label='Баны',
        )[0]

        for index, (organic_count, referral_count, blocked_count) in enumerate(data):
            total = organic_count + referral_count
            if total:
                axes.text(
                    index,
                    total + (max_value * 0.03),
                    str(total),
                    horizontalalignment='center',
                    color='#0f172a',
                    fontsize=9,
                    fontweight='bold',
                )
            if blocked_count:
                axes.text(
                    index,
                    blocked_count + (max_value * 0.05),
                    str(blocked_count),
                    horizontalalignment='center',
                    color='#b91c1c',
                    fontsize=9,
                    fontweight='bold',
                )

        axes.legend(
            handles=[
                mpatches.Patch(
                    color='#2563eb',
                    label='Органика',
                ),
                mpatches.Patch(
                    color='#10b981',
                    label='Рефералы',
                ),
                line,
            ],
        )
