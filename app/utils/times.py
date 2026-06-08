from datetime import date, timedelta


def get_times() -> tuple[date]:
    today = date.today()
    week_ago = today - timedelta(days=6)
    month_ago = today - timedelta(days=30)

    return today, week_ago, month_ago
