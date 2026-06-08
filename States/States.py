from aiogram.fsm.state import StatesGroup, State


class LinkAnswer(StatesGroup):
    getAnswer = State()


class AdminMailing(StatesGroup):
    waiting_message = State()
    waiting_buttons = State()
    confirm = State()


class AdminManagement(StatesGroup):
    grant_admin = State()
