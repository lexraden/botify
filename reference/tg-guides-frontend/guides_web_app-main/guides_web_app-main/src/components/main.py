from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery, SuccessfulPayment
import asyncio
import aiohttp
import uuid
TOKEN = "7783867804:AAGXzVtEVTgao4HtQZlpJf8SwHAbRh7e67o"
API_URL = "https://guides.ledokol.it/api/v1/user-profile"
ADD_REFERRAL_URL = f"{API_URL}/add-referral"
CHECK_USER_URL = f"{API_URL}/check-user"
AUTH_URL = "https://guides.ledokol.it/api/v1/auth/init"
COMPLETE_PURCHASE_URL = "https://guides.ledokol.it/api/v1/guides/payment-success"
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

async def check_user_exists(username: str):
    """Проверка, зарегистрирован ли пользователь."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CHECK_USER_URL}/{username}") as response:
            print(response)
            if response.status == 200:
                data = await response.json()
                return data  # Возвращаем данные пользователя, если он найден
            return None
async def get_auth_token(user_id, username):
    async with aiohttp.ClientSession() as session:
        payload = {
            'id': user_id,
            'username': username
        }
        async with session.post(AUTH_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('token')
            return None

# Завершение покупки
async def complete_purchase(guide_id: int, person_id: int, token: str):
    async with aiohttp.ClientSession() as session:
        guide_id = int(guide_id) 
        person_id = int(person_id)
        print(guide_id)
        print(person_id)
        headers = {
            'Authorization': f'{token}',  # Передаем токен в заголовке
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = {
            "guideId": guide_id,
            "personId": person_id
        }
        async with session.post(COMPLETE_PURCHASE_URL, data=payload, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_message = await response.text()
                return {'error': error_message}

@router.message(CommandStart())
async def start_command(message: types.Message, command: CommandStart):
    username = message.from_user.username
    if not username:
        await message.answer("Ваш Telegram профиль не имеет username, пожалуйста установите его.")
        return
    
    # Проверяем, зарегистрирован ли пользователь
    user_data = await check_user_exists(username)
    print(user_data)
    if user_data:
        url_button = InlineKeyboardButton(text="Open MiniApp", url="https://t.me/irlguides_bot/main")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [url_button] 
            ]
        )
        await message.answer("Вы уже зарегистрированы. Нажмите на кнопку ниже, чтобы открыть MiniApp:", reply_markup=keyboard)
        return

    # Если пользователь не зарегистрирован, проверяем реферальный код
    if command.args:
        referral_code = command.args
        async with aiohttp.ClientSession() as session:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            params = {
                'ref': referral_code  # Передаем реферальный код как параметр запроса
            }
            payload = {
                'id': message.from_user.id,  # Используем ID пользователя из Telegram
                'username': username
            }
            async with session.post(API_URL, json=payload, params=params, headers=headers) as response:
                if response.status == 200:
                    await message.answer(f"Вы успешно зарегистрированы по реферальной ссылке!")
                    url_button = InlineKeyboardButton(text="Open MiniApp", url="https://t.me/irlguides_bot/main")
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [url_button]
                        ]
                    )
                    await message.answer("Нажмите на кнопку ниже, чтобы открыть MiniApp:", reply_markup=keyboard)
                else:
                    error_message = await response.text()
                    await message.answer(f"Произошла ошибка при регистрации реферала")
    else:
        if user_data:
            url_button = InlineKeyboardButton(text="Open MiniApp", url="https://t.me/irlguides_bot/main")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [url_button] 
                ]
            )
            await message.answer("Вы уже зарегистрированы. Нажмите на кнопку ниже, чтобы открыть MiniApp:", reply_markup=keyboard)
            return
        else:
            url_button = InlineKeyboardButton(text="Open MiniApp", url="https://t.me/irlguides_bot/main")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [url_button] 
                ]
            )
            await message.answer("Добро пожаловать!",reply_markup=keyboard)
@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Обработка успешной оплаты
@router.message()
async def handle_successful_payment(message: types.Message):
    """Обработка успешной оплаты"""
    if message.successful_payment:
        guide_id = int(message.successful_payment.invoice_payload.split('-')[-1])
        person_id = message.from_user.id
        
        # Получаем токен авторизации
        token = await get_auth_token(person_id, message.from_user.username)
        if not token:
            await message.answer("Ошибка авторизации. Не удалось получить токен.")
            return
        
        # Отправляем запрос на завершение покупки
        response = await complete_purchase(guide_id, person_id, token)
        
        if response and 'error' not in response:
            await message.answer("Покупка завершена успешно!")
        else:
            await message.answer(f"Ошибка при завершении покупки: {response.get('error')}")


async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

