import asyncio
import random
import logging
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
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

# ===== СПИСОК ЭМОДЗИ ДЛЯ КАПЧИ =====
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

# ===== БОКОВАЯ ПАНЕЛЬ (Reply Keyboard) =====
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Вернуться в меню")],
            [KeyboardButton(text="⏳ Проверить очередь")],
            [KeyboardButton(text="💸 Баланс")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard

# ===== ИНЛАЙН МЕНЮ =====
def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Режим: ФБХ", callback_data="mode_fbx")],
        [InlineKeyboardButton(text="📲 Сдать Esim", callback_data="sell_esim"), 
         InlineKeyboardButton(text="💾 Архив", callback_data="archive")],
        [InlineKeyboardButton(text="⏳ Очередь", callback_data="queue"), 
         InlineKeyboardButton(text="💸 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="help")]
    ])
    return keyboard

def get_operators_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 MTS", callback_data="op_mts"), 
         InlineKeyboardButton(text="⚫️ T2", callback_data="op_t2")],
        [InlineKeyboardButton(text="🟡 Билайн", callback_data="op_beeline"), 
         InlineKeyboardButton(text="⚪️ Dobroсвязь", callback_data="op_dobro")],
        [InlineKeyboardButton(text="🔶 Миранда", callback_data="op_miranda"), 
         InlineKeyboardButton(text="🔷 Газпром", callback_data="op_gazprom")],
        [InlineKeyboardButton(text="🟢 Сбер", callback_data="op_sber"), 
         InlineKeyboardButton(text="🔵 ВТБ", callback_data="op_vtb")],
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
            f"Попробуйте снова через <b>{remaining} минут</b>.",
            reply_markup=get_main_keyboard()
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
        await callback.message.answer("✅ <b>Отлично! Капча пройдена!</b>", reply_markup=get_main_keyboard())
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
        "💲 <b>Добро пожаловать в ESIM PRIME</b> 💲\n\n"
        "⚡️ <b>Текущая ставка: ФБХ</b>\n"
        "<i>eSIM оплачивается моментально</i>\n\n"
        "⚠️ <b>Внимание!</b>\n"
        "<i>Берем только оплачиваемые eSIM.</i>\n\n"
        "📊 <b>Текущие цены (ФБХ):</b>\n"
        "🔴 MTS - 16$ / слет: 3.2$\n"
        "⚫️ T2 - 18$ / слет: 3.6$\n"
        "🟡 Билайн - 20$ / слет: 4$\n"
        "⚪️ Dobroсвязь - 18$ / слет: 3.6$\n"
        "🔶 Миранда - 19$ / слет: 3.7$\n"
        "🔷 Газпром - 22$ / слет: 4.2$\n"
        "🟢 Сбер - 17$ / слет: 3.3$\n"
        "🔵 ВТБ - 22$ / слет: 4.2$\n\n"
        "📌 <b>Дополнительные режимы:</b>\n"
        "• <b>БХ</b> (5 минут) → +3.5$ к каждому оператору\n"
        "• <b>Hold</b> (30 минут) → +5.5$ к каждому оператору\n\n"
        "⏳ <b>Очередь:</b> НИЗКАЯ\n"
        "<i>QR принимаются в течение 5 минут</i>\n\n"
        "👇 <b>Выберите режим сдачи:</b>"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await show_main_menu(callback.message)
    await callback.answer()

# ===== РЕЖИМ ФБХ =====
@dp.callback_query(F.data == "mode_fbx")
async def mode_fbx(callback: types.CallbackQuery):
    text = (
        "⚡️ <b>Режим: ФБХ</b>\n\n"
        "✅ Моментальная оплата\n"
        "✅ Без комиссии\n"
        "✅ Выплата в течение 2-5 минут\n\n"
        "💰 <b>Текущие цены:</b>\n"
        "🔴 MTS - 16$ / слет: 3.2$\n"
        "⚫️ T2 - 18$ / слет: 3.6$\n"
        "🟡 Билайн - 20$ / слет: 4$\n"
        "⚪️ Dobroсвязь - 18$ / слет: 3.6$\n"
        "🔶 Миранда - 19$ / слет: 3.7$\n"
        "🔷 Газпром - 22$ / слет: 4.2$\n"
        "🟢 Сбер - 17$ / слет: 3.3$\n"
        "🔵 ВТБ - 22$ / слет: 4.2$\n\n"
        "🔄 <i>Для смены режима используйте главное меню</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ===== СДАТЬ ESIM =====
@dp.callback_query(F.data == "sell_esim")
async def sell_esim(callback: types.CallbackQuery):
    text = (
        "📲 <b>Сдать eSIM</b>\n\n"
        "<i>Выберите оператора:</i>\n\n"
        "🔴 MTS - 16$ (слет: 3.2$)\n"
        "⚫️ T2 - 18$ (слет: 3.6$)\n"
        "🟡 Билайн - 20$ (слет: 4$)\n"
        "⚪️ Dobroсвязь - 18$ (слет: 3.6$)\n"
        "🔶 Миранда - 19$ (слет: 3.7$)\n"
        "🔷 Газпром - 22$ (слет: 4.2$)\n"
        "🟢 Сбер - 17$ (слет: 3.3$)\n"
        "🔵 ВТБ - 22$ (слет: 4.2$)"
    )
    await callback.message.edit_text(text, reply_markup=get_operators_keyboard())
    await callback.answer()

# ===== ВЫБОР ОПЕРАТОРА =====
@dp.callback_query(F.data.startswith("op_"))
async def select_operator(callback: types.CallbackQuery):
    operator_map = {
        "op_mts": "MTS",
        "op_t2": "T2",
        "op_beeline": "Билайн",
        "op_dobro": "Dobroсвязь",
        "op_miranda": "Миранда",
        "op_gazprom": "Газпром",
        "op_sber": "Сбер",
        "op_vtb": "ВТБ"
    }
    operator = operator_map.get(callback.data, "Неизвестно")
    
    prices = {
        "MTS": "16$",
        "T2": "18$",
        "Билайн": "20$",
        "Dobroсвязь": "18$",
        "Миранда": "19$",
        "Газпром": "22$",
        "Сбер": "17$",
        "ВТБ": "22$"
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить сдачу", callback_data=f"confirm_{callback.data}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_esim")]
    ])
    
    await callback.message.edit_text(
        f"📲 <b>Сдать eSIM</b>\n\n"
        f"Оператор: <b>{operator}</b>\n"
        f"Цена: <b>{prices.get(operator, '15$')}</b>\n\n"
        f"<i>Для подтверждения нажмите кнопку ниже</i>",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_sell(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "✅ <b>Заявка принята!</b>\n\n"
        "⏳ Ожидайте обработки.\n"
        "📊 Среднее время: <b>2-5 минут</b>\n\n"
        "💬 <i>Уведомление придет автоматически</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ])
    )
    await callback.answer("✅ Заявка отправлена!", show_alert=True)

# ===== АРХИВ =====
@dp.callback_query(F.data == "archive")
async def archive(callback: types.CallbackQuery):
    text = (
        "💾 <b>Архив сданных eSIM</b>\n\n"
        "📊 <b>Ваша статистика:</b>\n"
        "• Всего сдано: <b>0</b>\n"
        "• Ожидается: <b>0</b>\n"
        "• Завершено: <b>0</b>\n\n"
        "📅 <b>Последние операции:</b>\n"
        "<i>Нет операций</i>\n\n"
        "ℹ️ <i>История появится после первой сдачи</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ===== ОЧЕРЕДЬ =====
@dp.callback_query(F.data == "queue")
async def queue(callback: types.CallbackQuery):
    text = (
        "⏳ <b>Текущая очередь</b>\n\n"
        "📊 <b>Статистика:</b>\n"
        "• В очереди: <b>0</b>\n"
        "• Ожидают QR: <b>0</b>\n"
        "• В обработке: <b>0</b>\n\n"
        "📈 <b>Прогноз:</b>\n"
        "• Среднее время: <b>2-5 минут</b>\n"
        "• Очередь: <b>НИЗКАЯ</b>\n\n"
        "🕒 <i>QR принимаются в течение 5 минут</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="queue")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ===== БАЛАНС =====
@dp.callback_query(F.data == "balance")
async def balance(callback: types.CallbackQuery):
    text = (
        "💸 <b>Ваш баланс</b>\n\n"
        "💰 Баланс: <b>0.00$</b>\n"
        "🔄 Заблокировано: <b>0.00$</b>\n"
        "📊 Доступно: <b>0.00$</b>\n\n"
        "📈 <b>Статистика:</b>\n"
        "• Всего заработано: <b>0.00$</b>\n"
        "• Последняя выплата: <b>—</b>\n\n"
        "💳 <i>Вывод средств доступен от 5$</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="balance")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ===== ПОМОЩЬ =====
@dp.callback_query(F.data == "help")
async def show_help(callback: types.CallbackQuery):
    text = (
        "🆘 <b>Помощь</b>\n\n"
        "📌 <b>Как сдать eSIM:</b>\n"
        "1️⃣ Нажмите «📲 Сдать Esim»\n"
        "2️⃣ Выберите оператора\n"
        "3️⃣ Подтвердите заявку\n"
        "4️⃣ Ожидайте выплату\n\n"
        "⚡️ <b>Режимы сдачи:</b>\n"
        "• <b>ФБХ</b> — моментальная оплата\n"
        "• <b>БХ</b> — без холда (5 минут)\n"
        "• <b>Hold</b> — с холдом (30 минут)\n\n"
        "📞 <b>Контакты:</b>\n"
        "👤 <a href='https://t.me/erwins_gr_bot'>Поддержка</a>\n"
        "📢 <a href='https://t.me/erwins_gb_bot'>Новости</a>\n\n"
        "⚠️ <i>По всем вопросам обращайтесь в поддержку</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()

# ===== КОМАНДА /CHECK (ОЧЕРЕДЬ) =====
@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 Сначала пройдите капчу! Напишите /start")
        return
    
    text = (
        "⏳ <b>Текущая очередь</b>\n\n"
        "📊 <b>Статистика:</b>\n"
        "• В очереди: <b>0</b>\n"
        "• Ожидают QR: <b>0</b>\n"
        "• В обработке: <b>0</b>\n\n"
        "📈 <b>Прогноз:</b>\n"
        "• Среднее время: <b>2-5 минут</b>\n"
        "• Очередь: <b>НИЗКАЯ</b>"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

# ===== ОБЫЧНЫЕ СООБЩЕНИЯ =====
@dp.message(F.text == "🏠 Вернуться в меню")
async def back_to_menu_text(message: types.Message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 Сначала пройдите капчу! Напишите /start")
        return
    
    await show_main_menu(message)

@dp.message(F.text == "⏳ Проверить очередь")
async def check_queue_text(message: types.Message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 Сначала пройдите капчу! Напишите /start")
        return
    
    text = (
        "⏳ <b>Текущая очередь</b>\n\n"
        "📊 <b>Статистика:</b>\n"
        "• В очереди: <b>0</b>\n"
        "• Ожидают QR: <b>0</b>\n"
        "• В обработке: <b>0</b>\n\n"
        "📈 <b>Прогноз:</b>\n"
        "• Среднее время: <b>2-5 минут</b>\n"
        "• Очередь: <b>НИЗКАЯ</b>"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(F.text == "💸 Баланс")
async def balance_text(message: types.Message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 Сначала пройдите капчу! Напишите /start")
        return
    
    text = (
        "💸 <b>Ваш баланс</b>\n\n"
        "💰 Баланс: <b>0.00$</b>\n"
        "🔄 Заблокировано: <b>0.00$</b>\n"
        "📊 Доступно: <b>0.00$</b>\n\n"
        "📈 <b>Статистика:</b>\n"
        "• Всего заработано: <b>0.00$</b>\n"
        "• Последняя выплата: <b>—</b>"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

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
    print("🤖 Бот ESIM PRIME запущен!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
