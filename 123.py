import random
import logging
import asyncio
from aiogram import Bot, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram import Dispatcher, Router
from aiogram.filters import Command
import requests

# Инициализация логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token="8042451707:AAEFB7T27NS9NqhgrcYXRkOQQ1jbCMghIXE")
dp = Dispatcher()  # Используем новый способ создания Dispatcher
router = Router()  # Новый Router для обработки callback

# Пример комнаты
rooms = {
    'room_1': {"stake": 5, "player_1": None, "player_2": None},
    'room_2': {"stake": 10, "player_1": None, "player_2": None},
    'room_3': {"stake": 15, "player_1": None, "player_2": None},
    'room_4': {"stake": 20, "player_1": None, "player_2": None},
    'room_5': {"stake": 25, "player_1": None, "player_2": None},
}

# Ваш API-ключ для CryptoBot
CRYPTOBOT_API_KEY = '296585:AAaiFPAMqpKsH6mPUXF83oorUQZb6igDxRt'


# Функция для получения адреса депозита через API CryptoBot
def get_crypto_deposit_address(currency='USDT', blockchain='ERC20'):
    url = f'https://pay.crypt.bot/api/get_deposit_address'
    headers = {
        'Crypto-Pay-API-Token': CRYPTOBOT_API_KEY  # API-ключ в заголовке
    }
    params = {
        'currency': 'USDT',  # Например, USDT
        'blockchain': 'ERC-20'  # Например, ERC-20
    }
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return data.get('address', None)  # Возвращаем адрес для депозита
    else:
        logger.error(f"Ошибка при запросе адреса депозита: {response.status_code}, {response.text}")
        return None  # Если не удалось получить адрес, возвращаем None

# Генерация клавиатуры с комнатами
def generate_rooms_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for room_id, room in rooms.items():
        # Проверяем, сколько игроков в комнате
        players_in_room = sum([1 for player in [room["player_1"], room["player_2"]] if player is not None])
        status = f"{players_in_room}/2"  # Статус комнаты в формате 1/2 или 0/2
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"Комната {room_id[-1]}: {room['stake']}$ ({status})",
                callback_data=f"join_{room_id}"  # Передаем room_id через callback_data
            )
        ])
    return keyboard


# Обработчик команды /start
@router.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = generate_rooms_keyboard()
    await message.answer("Выберите комнату для игры:", reply_markup=keyboard)


# Обработчик нажатия на кнопку
@router.callback_query(lambda c: c.data.startswith('join_'))
async def join_room_handler(callback_query: CallbackQuery):
    room_id = callback_query.data[5:]  # Извлекаем room_id из callback_data
    if room_id in rooms:
        room = rooms[room_id]
        if room["player_1"] is None:
            # Если нет первого игрока, присоединим его как player_1
            room["player_1"] = callback_query.from_user.id
            await callback_query.message.answer(
                f"Вы присоединились к комнате {room_id} с номиналом ставки {room['stake']}$")
        elif room["player_2"] is None:
            # Если есть первый игрок, но нет второго
            room["player_2"] = callback_query.from_user.id
            await callback_query.message.answer(
                f"Вы присоединились ко второй ячейке комнаты {room_id} с номиналом ставки {room['stake']}$")
            await play_game(room_id)  # Запуск игры
        else:
            await callback_query.message.answer(f"Комната {room_id} уже занята.")
    else:
        await callback_query.message.answer(f"Комната {room_id} не найдена.")


# Функция для отправки анимированного кубика и получения результата
async def dice_roll_animation(player_1, player_2):
    # Отправляем анимированные кубики для игрока 1
    message_1 = await bot.send_dice(chat_id=player_1)
    result_1 = message_1.dice.value

    # Отправляем анимированные кубики для игрока 2
    message_2 = await bot.send_dice(chat_id=player_2)
    result_2 = message_2.dice.value

    return result_1, result_2


# Функция для подсчета победителя
async def play_game(room_id):
    room = rooms[room_id]
    player_1 = room["player_1"]
    player_2 = room["player_2"]

    # Отправляем анимированные кубики и получаем результаты
    result_1, result_2 = await dice_roll_animation(player_1, player_2)

    # Подсчет победителя
    if result_1 > result_2:
        winner = "Игрок 1"
    elif result_1 < result_2:
        winner = "Игрок 2"
    else:
        winner = "Ничья"

    logger.info(
        f"Игра в комнате {room_id} завершена. Победитель: {winner}. Результаты: Игрок 1 - {result_1}, Игрок 2 - {result_2}")

    # Оповещаем игроков о победителе
    await bot.send_message(player_1, f"Игра завершена! Ваш результат: {result_1}. Победитель: {winner}.")
    await bot.send_message(player_2, f"Игра завершена! Ваш результат: {result_2}. Победитель: {winner}.")

    # Очищаем комнату
    room["player_1"] = None
    room["player_2"] = None

    # Генерация клавиатуры с обновленными данными о комнатах
    keyboard = generate_rooms_keyboard()
    # Обновляем сообщение с новой клавиатурой
    await bot.send_message(player_1, "Игра завершена. Вы можете присоединиться к новой игре.", reply_markup=keyboard)
    await bot.send_message(player_2, "Игра завершена. Вы можете присоединиться к новой игре.", reply_markup=keyboard)


# Обработчик команды /deposit для получения адреса депозита
@router.message(Command("deposit"))
async def deposit(message: types.Message):
    user_id = message.from_user.id
    deposit_address = get_crypto_deposit_address()

    if deposit_address:
        await message.answer(
            f"Для депозита отправьте криптовалюту на следующий адрес:\n{deposit_address}"
        )
    else:
        await message.answer("Не удалось получить адрес для депозита. Попробуйте позже.")


# Регистрация обработчиков в диспетчере
dp.include_router(router)


# Запуск бота с использованием asyncio
async def on_start():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(on_start())
