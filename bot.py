import asyncio
import random
import logging
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8836390065:AAGHrl26Sz5k-zgswXwgNNlIe4Xaqjn2ta0"

# ===== ИНИЦИАЛИЗАЦИЯ =====
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)

# ===== СОСТОЯНИЯ FSM =====
class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

class MenuState(StatesGroup):
    main_menu = State()

# ===== ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ =====
USER_DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_user_data()

def get_user_state(user_id: int):
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "attempts": 0,
            "blocked_until": None,
            "passed": False
        }
        save_user_data(user_data)
    return user_data[user_id_str]

def save_user_state(user_id: int):
    save_user_data(user_data)

# ===== СПИСОК ЭМОДЗИ ПО КАТЕГОРИЯМ =====
EMOJIS = {
    "фрукты": ["🍎", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍒", "🍑", "🥭", "🍍", "🥝"],
    "животные": ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮"],
    "транспорт": ["🚗", "🚕", "🚙", "🚌", "🚎", "🏎️", "🚓", "🚑", "🚒", "🚐", "🛻", "🚚"],
    "еда": ["🍕", "🍔", "🍟", "🌭", "🥪", "🌮", "🌯", "🥙", "🧆", "🥚", "🍳", "🥞"],
    "природа": ["🌺", "🌸", "🌷", "🌻", "🌹", "🌿", "☘️", "🍀", "🌳", "🌲", "🌵", "🌴"],
    "спорт": ["⚽", "🏀", "🏈", "⚾", "🥎", "🎾", "🏐", "🏉", "🥏", "🎱", "🏓", "🏸"],
    "техника": ["💻", "🖥️", "⌨️", "🖱️", "📱", "📲", "💿", "📀", "🎮", "🕹️", "📷", "📹"]
}

def generate_captcha():
    category = random.choice(list(EMOJIS.keys()))
    emojis = EMOJIS[category]
    target_emoji = random.choice(emojis)
    other_emojis = [e for e in emojis if e != target_emoji]
    random.shuffle(other_emojis)
    options = [target_emoji] + other_emojis[:3]
    random.shuffle(options)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=options[0], callback_data=f"captcha_{options[0]}"), 
         InlineKeyboardButton(text=options[1], callback_data=f"captcha_{options[1]}")],
        [InlineKeyboardButton(text=options[2], callback_data=f"captcha_{options[2]}"), 
         InlineKeyboardButton(text=options[3], callback_data=f"captcha_{options[3]}")]
    ])
    
    return target_emoji, keyboard, category

# ===== МЕНЮ =====
def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Сдать eSIM", callback_data="sell_esim")],
        [InlineKeyboardButton(text="🔄 Режим сдачи: ФБХ", callback_data="change_mode")],
        [InlineKeyboardButton(text="📊 Актуальная информация", callback_data="info")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="help")]
    ])
    return keyboard

def get_operators_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 МТС", callback_data="op_mts"), 
         InlineKeyboardButton(text="🔵 Билайн", callback_data="op_beeline")],
        [InlineKeyboardButton(text="🟢 Т2", callback_data="op_t2"), 
         InlineKeyboardButton(text="🟡 МТС WORLD", callback_data="op_mts_world")],
        [InlineKeyboardButton(text="⚪ Добросовестный", callback_data="op_dobro"), 
         InlineKeyboardButton(text="🔶 Миранда", callback_data="op_miranda")],
        [InlineKeyboardButton(text="🔷 Газпром", callback_data="op_gazprom"), 
         InlineKeyboardButton(text="💳 ТБанк", callback_data="op_tbank")],
        [InlineKeyboardButton(text="🏦 ВТБ", callback_data="op_vtb")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard

def get_mode_keyboard(current_mode):
    text = "🔄 ФБХ" if current_mode == "ФБХ" else "🔄 БХ"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="toggle_mode")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard

# ===== ОБРАБОТЧИК КОМАНДЫ /START =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    username = message.from_user.username or message.from_user.first_name
    
    if user_state["blocked_until"] and datetime.now() < datetime.fromisoformat(user_state["blocked_until"]):
        remaining = (datetime.fromisoformat(user_state["blocked_until"]) - datetime.now()).seconds // 60
        await message.answer(
            f"⛔ Вы слишком много раз ошиблись!\n"
            f"Попробуйте снова через <b>{remaining} минут</b>."
        )
        return
    
    if user_state["passed"]:
        await show_main_menu(message)
        return
    
    if user_state["blocked_until"] and datetime.now() >= datetime.fromisoformat(user_state["blocked_until"]):
        user_state["attempts"] = 0
        user_state["blocked_until"] = None
        save_user_state(user_id)
    
    target_emoji, keyboard, category = generate_captcha()
    await state.set_state(CaptchaState.waiting_for_captcha)
    await state.update_data(target_emoji=target_emoji, attempts=user_state["attempts"])
    
    await message.answer(
        f"👋 <b>Привет, @{username}!</b>\n\n"
        f"🔐 <b>Пройдите капчу для работы с ботом</b>\n\n"
        f"Выберите кнопку с этим смайликом: <b>{target_emoji}</b>\n"
        f"<i>(категория: {category})</i>\n\n"
        f"⚠️ Попыток осталось: <b>{3 - user_state['attempts']}</b>",
        reply_markup=keyboard
    )

# ===== КАПЧА =====
@dp.callback_query(F.data.startswith("captcha_"), CaptchaState.waiting_for_captcha)
async def process_captcha(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_state = get_user_state(user_id)
    fsm_data = await state.get_data()
    target_emoji = fsm_data.get("target_emoji")
    attempts = fsm_data.get("attempts", 0)
    selected_emoji = callback.data.replace("captcha_", "")
    
    if user_state["blocked_until"] and datetime.now() < datetime.fromisoformat(user_state["blocked_until"]):
        await callback.answer("⛔ Вы заблокированы! Подождите.", show_alert=True)
        return
    
    if selected_emoji == target_emoji:
        user_state["passed"] = True
        user_state["attempts"] = 0
        user_state["blocked_until"] = None
        save_user_state(user_id)
        await callback.message.delete()
        await callback.message.answer("✅ <b>Отлично! Капча пройдена!</b>")
        await show_main_menu(callback.message)
        await state.clear()
        await callback.answer("✅ Капча пройдена!", show_alert=True)
        return
    
    attempts += 1
    user_state["attempts"] = attempts
    save_user_state(user_id)
    
    if attempts >= 3:
        block_until = datetime.now() + timedelta(minutes=15)
        user_state["blocked_until"] = block_until.isoformat()
        save_user_state(user_id)
        await callback.message.edit_text(
            f"❌ <b>Вы использовали все 3 попытки!</b>\n\n"
            f"⛔ Доступ заблокирован до:\n"
            f"<b>{block_until.strftime('%H:%M:%S')}</b>\n\n"
            f"Попробуйте снова через 15 минут.",
            reply_markup=None
        )
        await state.clear()
        await callback.answer("⛔ Вы заблокированы на 15 минут!", show_alert=True)
        return
    
    target_emoji, keyboard, category = generate_captcha()
    await state.update_data(target_emoji=target_emoji, attempts=attempts)
    await callback.message.edit_text(
        f"❌ <b>Неверно! Попробуйте еще раз.</b>\n\n"
        f"🔐 <b>Пройдите капчу для работы с ботом</b>\n\n"
        f"Выберите кнопку с этим смайликом: <b>{target_emoji}</b>\n"
        f"<i>(категория: {category})</i>\n\n"
        f"⚠️ Попыток осталось: <b>{3 - attempts}</b>",
        reply_markup=keyboard
    )
    await callback.answer("❌ Неправильно!", show_alert=True)

# ===== ГЛАВНОЕ МЕНЮ =====
async def show_main_menu(message: types.Message):
    text = (
        "<b>🏠 Главное меню</b>\n\n"
        "Выберите действие:\n\n"
        "📱 <b>Сдать eSIM</b> - выбрать оператора\n"
        "🔄 <b>Режим сдачи: ФБХ</b> - моментальная оплата\n"
        "📊 <b>Актуальная информация</b> - текущие цены и статус\n"
        "🆘 <b>Помощь</b> - поддержка"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await show_main_menu(callback.message)
    await callback.answer()

# ===== СДАТЬ ESIM =====
@dp.callback_query(F.data == "sell_esim")
async def sell_esim(callback: types.CallbackQuery):
    text = (
        "<b>📱 Сдать eSIM</b>\n\n"
        "<i>Выберите оператора:</i>\n\n"
        "🔴 МТС - 15$\n"
        "🔵 Билайн - 18$\n"
        "🟢 Т2 - 16$\n"
        "🟡 МТС WORLD - 29$\n"
        "⚪ Добросовестный - 18$\n"
        "🔶 Миранда - 18$\n"
        "🔷 Газпром - 20$\n"
        "💳 ТБанк - 18$\n"
        "🏦 ВТБ - 20$"
    )
    await callback.message.edit_text(text, reply_markup=get_operators_keyboard())
    await callback.answer()

# ===== ВЫБОР ОПЕРАТОРА =====
@dp.callback_query(F.data.startswith("op_"))
async def select_operator(callback: types.CallbackQuery):
    operator_map = {
        "op_mts": "МТС",
        "op_beeline": "Билайн",
        "op_t2": "Т2",
        "op_mts_world": "МТС WORLD",
        "op_dobro": "Добросовестный",
        "op_miranda": "Миранда",
        "op_gazprom": "Газпром",
        "op_tbank": "ТБанк",
        "op_vtb": "ВТБ"
    }
    operator = operator_map.get(callback.data, "Неизвестно")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить сдачу", callback_data=f"confirm_{callback.data}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_esim")]
    ])
    
    await callback.message.edit_text(
        f"<b>📱 Сдать eSIM</b>\n\n"
        f"Оператор: <b>{operator}</b>\n"
        f"Цена: <b>15$</b>\n\n"
        f"<i>Для подтверждения нажмите кнопку ниже</i>",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_sell(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>✅ Заявка принята!</b>\n\n"
        "Ожидайте обработки.\n"
        "Среднее время ожидания: <b>2-5 минут</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ])
    )
    await callback.answer("✅ Заявка отправлена!", show_alert=True)

# ===== РЕЖИМ СДАЧИ =====
@dp.callback_query(F.data == "change_mode")
async def change_mode(callback: types.CallbackQuery):
    text = (
        "<b>🔄 Режим сдачи: ФБХ</b>\n\n"
        "В этом режиме сдача eSIM оплачивается <b>моментально</b>.\n"
        "В случае слета, мы выплачиваем компенсацию <b>3$</b>.\n\n"
        "⚠️ <i>Внимание: комиссия за вывод средств отсутствует.</i>\n\n"
        "<i>Для смены режима нажмите кнопку снизу.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_mode_keyboard("ФБХ"))
    await callback.answer()

@dp.callback_query(F.data == "toggle_mode")
async def toggle_mode(callback: types.CallbackQuery):
    text = (
        "<b>🔄 Режим сдачи: БХ</b>\n\n"
        "В этом режиме холда нет, оплата производится даже за 5 минут.\n\n"
        "<i>Для смены режима нажмите кнопку снизу.</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ФБХ", callback_data="toggle_mode_back")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "toggle_mode_back")
async def toggle_mode_back(callback: types.CallbackQuery):
    text = (
        "<b>🔄 Режим сдачи: ФБХ</b>\n\n"
        "В этом режиме сдача eSIM оплачивается <b>моментально</b>.\n"
        "В случае слета, мы выплачиваем компенсацию <b>3$</b>.\n\n"
        "⚠️ <i>Внимание: комиссия за вывод средств отсутствует.</i>\n\n"
        "<i>Для смены режима нажмите кнопку снизу.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_mode_keyboard("ФБХ"))
    await callback.answer()

# ===== ИНФОРМАЦИЯ =====
@dp.callback_query(F.data == "info")
async def show_info(callback: types.CallbackQuery):
    text = (
        "<b>📊 Актуальная информация</b>\n\n"
        "📱 <b>Цены на eSIM:</b>\n"
        "🔴 МТС - 15$\n"
        "🔵 Билайн - 18$\n"
        "🟢 Т2 - 16$\n"
        "🟡 МТС WORLD - 29$\n"
        "⚪ Добросовестный - 18$\n"
        "🔶 Миранда - 18$\n"
        "🔷 Газпром - 20$\n"
        "💳 ТБанк - 18$\n"
        "🏦 ВТБ - 20$\n\n"
        "📊 <b>Статистика:</b>\n"
        "• Всего сдано eSIM: <b>1,247</b>\n"
        "• Активных пользователей: <b>89</b>\n"
        "• Среднее время выплаты: <b>3 минуты</b>\n\n"
        "<i>Данные обновляются в реальном времени</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ===== ПОМОЩЬ =====
@dp.callback_query(F.data == "help")
async def show_help(callback: types.CallbackQuery):
    text = (
        "<b>🆘 Помощь</b>\n\n"
        "📱 <b>Как сдать eSIM:</b>\n"
        "1. Нажмите «Сдать eSIM»\n"
        "2. Выберите оператора\n"
        "3. Подтвердите заявку\n"
        "4. Ожидайте выплату\n\n"
        "💬 <b>Контакты поддержки:</b>\n"
        "👤 <a href='https://t.me/erwins_gr_bot'>Поддержка</a>\n"
        "📢 <a href='https://t.me/erwins_gb_bot'>Новости</a>\n\n"
        "⚠️ <i>По всем вопросам обращайтесь в поддержку</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()

# ===== ОБЫЧНЫЕ СООБЩЕНИЯ =====
@dp.message()
async def handle_other_messages(message: types.Message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 <b>Сначала пройдите капчу!</b>\nНапишите /start, чтобы начать.")
        return
    
    if user_state["blocked_until"] and datetime.now() < datetime.fromisoformat(user_state["blocked_until"]):
        remaining = (datetime.fromisoformat(user_state["blocked_until"]) - datetime.now()).seconds // 60
        await message.answer(f"⛔ Вы заблокированы!\nПопробуйте через <b>{remaining} минут</b>.")
        return
    
    await show_main_menu(message)

# ===== ЗАПУСК БОТА =====
async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
