import logging
import asyncio
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiocryptopay import Networks, AioCryptoPay
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import uuid

# Инициализация логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token="8042451707:AAEFB7T27NS9NqhgrcYXRkOQQ1jbCMghIXE")
dp = Dispatcher()
router = Router()

# Инициализация клиента AioCryptoPay для криптовалютных платежей
client = AioCryptoPay(token="296585:AAaiFPAMqpKsH6mPUXF83oorUQZb6igDxRt", network=Networks.MAIN_NET)

# Пример комнаты
rooms = {
    'room_1': {"stake": 5, "player_1": None, "player_2": None},
    'room_2': {"stake": 10, "player_1": None, "player_2": None},
    'room_3': {"stake": 15, "player_1": None, "player_2": None},
    'room_4': {"stake": 20, "player_1": None, "player_2": None},
    'room_5': {"stake": 25, "player_1": None, "player_2": None},
}

# Работа с данными пользователей в JSON
def load_data():
    try:
        with open("user_profiles.json", "r") as file:
            content = file.read().strip()
            if not content:
                return {"users": {}}
            return json.loads(content)
    except FileNotFoundError:
        return {"users": {}}
    except json.JSONDecodeError:
        logger.error("Error decoding JSON from the file, resetting file content.")
        return {"users": {}}

def save_data(data):
    with open("user_profiles.json", "w") as file:
        json.dump(data, file, indent=4)

def add_new_user(user_id):
    data = load_data()
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "tg_id": user_id,
            "balance": 0.0,
            "deposits": []
        }
        save_data(data)
        return True
    return False

def generate_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать комнату", callback_data="rooms")],
        [InlineKeyboardButton(text="Внести депозит", callback_data="deposit")],
        [InlineKeyboardButton(text="Вывести средства", callback_data="withdraw")],
    ])
    return keyboard

def generate_rooms_keyboard(user_id=None):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for room_id, room in rooms.items():
        players_in_room = sum([1 for player in [room["player_1"], room["player_2"]] if player is not None])
        status = f"{players_in_room}/2"
        keyboard.inline_keyboard.append([InlineKeyboardButton(
            text=f"Комната {room_id[-1]}: {room['stake']}$ ({status})",
            callback_data=f"join_{room_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Выбрать депозит", callback_data="choose_deposit")])
    if user_id:
        user_data = load_data()
        user_profile = user_data.get("users", {}).get(str(user_id), {})
        balance = user_profile.get("balance", 0)
        if balance > 0:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text="Вывести средства на Cryptobot", callback_data="withdraw_funds")])
    return keyboard

def generate_withdraw_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вывести средства на Cryptobot", callback_data="withdraw_funds")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_rooms")]
    ])

def generate_deposit_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 USDT", callback_data="choose_deposit_5")],
        [InlineKeyboardButton(text="10 USDT", callback_data="choose_deposit_10")],
        [InlineKeyboardButton(text="20 USDT", callback_data="choose_deposit_20")],
        [InlineKeyboardButton(text="50 USDT", callback_data="choose_deposit_50")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_rooms")],
    ])

@router.callback_query(lambda c: c.data == "rooms")
async def rooms_handler(callback_query: CallbackQuery):
    keyboard = generate_rooms_keyboard(callback_query.from_user.id)
    await callback_query.message.answer("Выберите комнату:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "deposit")
async def deposit_handler(callback_query: CallbackQuery):
    keyboard = generate_deposit_keyboard()
    await callback_query.message.answer("Выберите депозит:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "withdraw")
async def withdraw_handler(callback_query: CallbackQuery):
    keyboard = generate_withdraw_keyboard()
    await callback_query.message.answer("Выберите действие для вывода средств:", reply_markup=keyboard)

import uuid  # Для генерации уникального spend_id

@router.callback_query(lambda c: c.data == "withdraw_funds")
async def withdraw_funds_handler(callback_query: CallbackQuery):
    """Обработчик вывода средств."""
    user_id = callback_query.from_user.id
    user_data = load_data()
    user_profile = user_data.get("users", {}).get(str(user_id), {})
    balance = user_profile.get("balance", 0)

    if balance > 0:
        await callback_query.message.answer(
            f"Ваш баланс: {balance} USDT. Введите сумму для вывода:"
        )
    else:
        await callback_query.message.answer("У вас недостаточно средств для вывода.")

@router.message(lambda message: message.text.isdigit())
async def process_withdrawal_request(message: types.Message):
    """Обрабатывает запрос на вывод средств."""
    user_id = message.from_user.id
    withdrawal_amount = int(message.text)
    user_data = load_data()
    user_profile = user_data.get("users", {}).get(str(user_id), {})
    balance = user_profile.get("balance", 0)

    if withdrawal_amount <= balance:
        # Списываем средства с баланса пользователя
        user_profile["balance"] -= withdrawal_amount
        save_data(user_data)

        try:
            # Генерация уникального spend_id
            spend_id = str(uuid.uuid4())

            # Выполняем перевод через Cryptobot API
            transfer = await client.transfer(
                user_id=user_id,  # Используем Telegram ID клиента
                asset="USDT",
                amount=withdrawal_amount,
                spend_id=spend_id,
            )

            # Успешный перевод
            await message.answer(
                f"Вы успешно вывели {withdrawal_amount} USDT на ваш Cryptobot кошелек."
            )
        except Exception as e:
            # Логируем ошибку и возвращаем баланс
            logging.error(f"Ошибка при выводе средств: {e}")
            user_profile["balance"] += withdrawal_amount
            save_data(user_data)
            await message.answer(
                "Произошла ошибка при выводе средств. Попробуйте еще раз позже."
            )
    else:
        await message.answer("Недостаточно средств для вывода.")

@router.callback_query(lambda c: c.data == "back_to_rooms")
async def back_to_rooms_handler(callback_query: CallbackQuery):
    keyboard = generate_rooms_keyboard(callback_query.from_user.id)
    await callback_query.message.answer("Выберите комнату для игры:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith("choose_deposit_"))
async def deposit_handler(callback_query: CallbackQuery):
    deposit = int(callback_query.data.split("_")[2])  # Извлекаем сумму депозита из callback data
    await callback_query.message.answer(f"Вы выбрали депозит {deposit} USDT.")

    # Создание счета для выбранного депозита
    invoice = await client.create_invoice(asset='USDT', amount=deposit)

    # Создание клавиатуры с кнопкой для оплаты
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {deposit} USDT", url=invoice.bot_invoice_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"CHECK|{invoice.invoice_id}")]
    ])

    await callback_query.message.answer(
        f"Вы выбрали депозит {deposit} USDT. Пожалуйста, используйте кнопку ниже для оплаты.",
        reply_markup=builder
    )

@router.callback_query(lambda c: c.data.startswith("CHECK|"))
async def check_invoice(call: CallbackQuery):
    invoice_id = int(call.data.split("|")[1])  # Извлекаем invoice_id из callback_data
    # Получаем инвойс по ID с фильтрацией по статусу 'paid'
    invoices = await client.get_invoices(invoice_ids=str(invoice_id), status="paid")

    if invoices:
        invoice = invoices[0]  # Получаем первый инвойс из списка
        # Удаляем сообщение с кнопкой проверки
        await call.message.delete()

        # Обновляем баланс пользователя
        user_id = call.from_user.id
        user_data = load_data()
        user_profile = user_data.get("users", {}).get(str(user_id), {})
        user_profile["balance"] += invoice.amount  # Добавляем сумму депозита на баланс
        save_data(user_data)

        # Уведомление пользователя об успешной оплате
        await call.message.answer(
            f"Оплата прошла успешно! Ваш баланс был пополнен на {invoice.amount} USDT."
        )
    else:
        # Если оплата не была найдена
        await call.answer("Оплата не обнаружена. Пожалуйста, проверьте статус или повторите оплату.")


def check_balance(user_id, stake):
    user_data = load_data()
    user_profile = user_data.get("users", {}).get(str(user_id), {})
    user_balance = user_profile.get("balance", 0)
    if user_balance < stake:
        return False
    return True

@router.callback_query(lambda c: c.data.startswith('join_'))
async def join_room_handler(callback_query: CallbackQuery):
    room_id = callback_query.data[5:]
    if room_id in rooms:
        room = rooms[room_id]
        stake = room["stake"]
        user_id = callback_query.from_user.id
        if not check_balance(user_id, stake):
            await callback_query.message.answer(
                f"У вас недостаточно средств для входа в комнату {room_id}. Пожалуйста, пополните баланс.")
            return
        if room["player_1"] is None:
            room["player_1"] = user_id
            await callback_query.message.answer(
                f"Вы присоединились к комнате {room_id} с номиналом ставки {stake}$")
        elif room["player_2"] is None:
            room["player_2"] = user_id
            await callback_query.message.answer(
                f"Вы присоединились ко второй ячейке комнаты {room_id} с номиналом ставки {stake}$")
            await play_game(room_id)
        else:
            await callback_query.message.answer(f"Комната {room_id} уже занята.")
    else:
        await callback_query.message.answer(f"Комната {room_id} не найдена.")

async def dice_roll_animation(player_1, player_2):
    message_1 = await bot.send_dice(chat_id=player_1)
    result_1 = message_1.dice.value
    message_2 = await bot.send_dice(chat_id=player_2)
    result_2 = message_2.dice.value
    return result_1, result_2

def deduct_balance(user_id, stake):
    user_data = load_data()
    user_profile = user_data.get("users", {}).get(str(user_id), {})
    user_balance = user_profile.get("balance", 0)
    if user_balance >= stake:
        user_profile["balance"] -= stake
        save_data(user_data)
        return True
    return False

async def process_payment_confirmation(user_id, deposit_amount):
    user_data = load_data()
    user_profile = user_data["users"].get(str(user_id), {})
    user_profile["balance"] += deposit_amount
    save_data(user_data)
    await bot.send_message(user_id, f"Ваш депозит {deposit_amount} USDT был зачислен на счет.")

async def play_game(room_id):
    room = rooms[room_id]
    player_1 = room["player_1"]
    player_2 = room["player_2"]
    stake_1 = room["stake"]
    stake_2 = room["stake"]
    if player_1:
        if not deduct_balance(player_1, stake_1):
            await bot.send_message(player_1, "Недостаточно средств для игры.")
            return
    if player_2:
        if not deduct_balance(player_2, stake_2):
            await bot.send_message(player_2, "Недостаточно средств для игры.")
            return
    result_1, result_2 = await dice_roll_animation(player_1, player_2)
    if result_1 > result_2:
        winner = player_1
        loser = player_2
        prize = stake_2 * 0.8
    elif result_1 < result_2:
        winner = player_2
        loser = player_1
        prize = stake_1 * 0.8
    else:
        winner = None
        prize = 0
    if winner:
        user_data = load_data()
        user_profile = user_data.get("users", {}).get(str(winner), {})
        user_profile["balance"] += (stake_1 if winner == player_1 else stake_2) + prize
        save_data(user_data)
        await bot.send_message(winner,
                               f"Вы выиграли! Ваш приз: {prize} USDT. Ваша ставка {stake_1 if winner == player_1 else stake_2} USDT возвращена.")
        await bot.send_message(loser, f"Вы проиграли. Ваша ставка {room['stake']} USDT списана.")
    else:
        user_data = load_data()
        if player_1:
            user_profile_1 = user_data.get("users", {}).get(str(player_1), {})
            user_profile_1["balance"] += stake_1
        if player_2:
            user_profile_2 = user_data.get("users", {}).get(str(player_2), {})
            user_profile_2["balance"] += stake_2
        save_data(user_data)
        await bot.send_message(player_1, f"Ничья! Ваша ставка {stake_1} USDT возвращена.")
        await bot.send_message(player_2, f"Ничья! Ваша ставка {stake_2} USDT возвращена.")
    logger.info(f"Игра в комнате {room_id} завершена. Победитель: {winner}, Приз: {prize}.")
    room["player_1"] = None
    room["player_2"] = None
    keyboard = generate_rooms_keyboard()
    if player_1:
        await bot.send_message(player_1, "Игра завершена. Вы можете присоединиться к новой игре.",
                               reply_markup=keyboard)
    if player_2:
        await bot.send_message(player_2, "Игра завершена. Вы можете присоединиться к новой игре.",
                               reply_markup=keyboard)

@router.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if add_new_user(user_id):
        await message.answer("Добро пожаловать! Ваш профиль был создан.")
    else:
        await message.answer("Вы уже зарегистрированы в системе.")
    keyboard = generate_main_menu_keyboard()
    await message.answer("Выберите действие:", reply_markup=keyboard)

dp.include_router(router)

async def on_start():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(on_start())
