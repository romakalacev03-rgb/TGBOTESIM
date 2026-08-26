import asyncio
import random
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8836390065:AAGHrl26Sz5k-zgswXwgNNlIe4Xaqjn2ta0"  # Замени на свой токен!

# ===== ИНИЦИАЛИЗАЦИЯ =====
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)

# ===== СОСТОЯНИЯ FSM =====
class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

# ===== ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ =====
user_data = {}

# ===== СПИСОК ЭМОДЗИ =====
EMOJIS = ["😀", "😁", "😂", "🤣", "😊", "😍", "🥰", "😘", "😗", "😙", "😚", "🙂", "🤗", "🤩", "🤔", "🤨", "😐", "😑", "😶", "🙄", "😏", "😣", "😥", "😮", "🤐", "😯", "😪", "😫", "😴", "😌", "😛", "😜", "😝", "🤤", "😒", "😓", "😔", "😕", "🙃", "🤑", "😲", "☹️", "🙁", "😖", "😞", "😟", "😤", "😢", "😭", "😦", "😧", "😨", "😩", "🤯", "😬", "😰", "😱", "🥵", "🥶", "😳", "🤪", "😵", "😡", "😠", "🤬"]

def generate_captcha():
    target_emoji = random.choice(EMOJIS)
    other_emojis = [e for e in EMOJIS if e != target_emoji]
    random.shuffle(other_emojis)
    options = [target_emoji] + other_emojis[:3]
    random.shuffle(options)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=options[0], callback_data=f"captcha_{options[0]}")],
        [InlineKeyboardButton(text=options[1], callback_data=f"captcha_{options[1]}")],
        [InlineKeyboardButton(text=options[2], callback_data=f"captcha_{options[2]}")],
        [InlineKeyboardButton(text=options[3], callback_data=f"captcha_{options[3]}")]
    ])
    
    return target_emoji, keyboard

def get_user_state(user_id: int):
    if user_id not in user_data:
        user_data[user_id] = {
            "attempts": 0,
            "blocked_until": None,
            "passed": False
        }
    return user_data[user_id]

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if user_state["blocked_until"] and datetime.now() < user_state["blocked_until"]:
        remaining = (user_state["blocked_until"] - datetime.now()).seconds // 60
        await message.answer(
            f"⛔ Вы слишком много раз ошиблись!\n"
            f"Попробуйте снова через <b>{remaining} минут</b>."
        )
        return
    
    if user_state["passed"]:
        await message.answer(
            "✅ <b>Добро пожаловать!</b>\n\n"
            "Вы уже прошли капчу. Бот готов к работе!"
        )
        return
    
    if user_state["blocked_until"] and datetime.now() >= user_state["blocked_until"]:
        user_state["attempts"] = 0
        user_state["blocked_until"] = None
    
    target_emoji, keyboard = generate_captcha()
    await state.set_state(CaptchaState.waiting_for_captcha)
    await state.update_data(target_emoji=target_emoji, attempts=user_state["attempts"])
    
    await message.answer(
        f"🔐 <b>Пожалуйста, пройдите капчу</b>\n\n"
        f"Найдите и выберите этот смайлик: <b>{target_emoji}</b>\n\n"
        f"⚠️ У вас осталось попыток: <b>{3 - user_state['attempts']}</b>",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("captcha_"), CaptchaState.waiting_for_captcha)
async def process_captcha(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_state = get_user_state(user_id)
    fsm_data = await state.get_data()
    target_emoji = fsm_data.get("target_emoji")
    attempts = fsm_data.get("attempts", 0)
    selected_emoji = callback.data.replace("captcha_", "")
    
    if user_state["blocked_until"] and datetime.now() < user_state["blocked_until"]:
        await callback.answer("⛔ Вы заблокированы! Подождите.", show_alert=True)
        return
    
    if selected_emoji == target_emoji:
        user_state["passed"] = True
        user_state["attempts"] = 0
        user_state["blocked_until"] = None
        await callback.message.delete()
        await callback.message.answer("✅ <b>Отлично! Капча пройдена!</b>\n\n🤖 Бот теперь полностью работает.")
        await state.clear()
        await callback.answer("✅ Капча пройдена!", show_alert=True)
        return
    
    attempts += 1
    user_state["attempts"] = attempts
    
    if attempts >= 3:
        block_until = datetime.now() + timedelta(minutes=15)
        user_state["blocked_until"] = block_until
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
    
    target_emoji, keyboard = generate_captcha()
    await state.update_data(target_emoji=target_emoji, attempts=attempts)
    await callback.message.edit_text(
        f"❌ <b>Неверно! Попробуйте еще раз.</b>\n\n"
        f"Найдите и выберите этот смайлик: <b>{target_emoji}</b>\n\n"
        f"⚠️ У вас осталось попыток: <b>{3 - attempts}</b>",
        reply_markup=keyboard
    )
    await callback.answer("❌ Неправильно!", show_alert=True)

@dp.message()
async def handle_other_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state["passed"]:
        await message.answer("🔐 <b>Сначала пройдите капчу!</b>\nНапишите /start, чтобы начать.")
        return
    
    if user_state["blocked_until"] and datetime.now() < user_state["blocked_until"]:
        remaining = (user_state["blocked_until"] - datetime.now()).seconds // 60
        await message.answer(f"⛔ Вы заблокированы!\nПопробуйте через <b>{remaining} минут</b>.")
        return
    
    await message.reply(f"✅ <b>Бот работает!</b>\n\nВы написали: <i>{message.text}</i>")

async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
