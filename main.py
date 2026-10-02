import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAW_KEYS = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_gender = {}
current_key_idx = 0

def get_current_client():
    global current_key_idx
    if not API_KEYS:
        raise ValueError("GEMINI_API_KEY не задан в настройках Render!")
    key = API_KEYS[current_key_idx % len(API_KEYS)]
    return genai.Client(api_key=key)

def get_system_prompt(gender: str) -> str:
    appeal = "любимый сын" if gender == "male" else "дочь моя, любимое дитя"

    return f"""
Ты — священный Оракул Асгарда и проводник мудрости Старшего Футарка.
Ты обращаешься к вопрошающему с глубокой божественной заботой, материнской и отеческой любовью, теплом и пониманием.

ОБЯЗАТЕЛЬНОЕ ОБРАЩЕНИЕ:
Всегда нежно используй обращение: «{appeal}».

ПРАВИЛА ОТВЕТА:
1. Выбери светлое божество, созвучное вопросу (Фрейя, Фригг, Бальдр, Идунн, мудрый Отец Один, добрый Тор-защитник).
2. Назови выпавшую руну Старшего Футарка (её скандинавский символ и благословенную суть).
3. Дай светлое толкование знака применительно к ситуации (1-2 предложения).
4. Огласи доброе, согревающее напутствие — прямое благословение богов.

СТРОГИЙ ШАБЛОН ОТВЕТА:
Глас: [Имя божества и теплое обращение со словами «{appeal}»]
Руна: [Символ, Название — созидательное значение]
Знамение: [Доброе толкование для ситуации]
Благословение богов: [Чуткое, поддерживающее напутствие]
"""

def get_gender_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌸 Дочь (женский)", callback_data="gender_female"),
            InlineKeyboardButton(text="⚔️ Сын (мужской)", callback_data="gender_male")
        ]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_gender[message.from_user.id] = "female"
    await message.answer(
        "Врата Асгарда распахнуты пред тобой с теплом и светом ✨\n\n"
        "Укажи, как богам обращаться к тебе:",
        reply_markup=get_gender_keyboard()
    )

@dp.callback_query(F.data.startswith("gender_"))
async def process_gender_callback(callback: types.CallbackQuery):
    if callback.data == "gender_female":
        user_gender[callback.from_user.id] = "female"
        await callback.message.edit_text("Боги приняли твой ответ. Спрашивай с легким сердцем, дочь моя, любимое дитя 🌸")
    else:
        user_gender[callback.from_user.id] = "male"
        await callback.message.edit_text("Боги приняли твой ответ. Задай свой вопрос, любимый сын ⚔️")
    await callback.answer()

@dp.message()
async def handle_message(message: types.Message):
    global current_key_idx
    if not message.text:
        return

    gender = user_gender.get(message.from_user.id, "female")
    prompt_text = f"{get_system_prompt(gender)}\n\nВопрос: {message.text}"
    
    total_keys = len(API_KEYS)
    last_err = "Нет доступных ключей"

    for _ in range(max(1, total_keys)):
        try:
            client = get_current_client()
            response = await client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt_text
            )
            if response and response.text:
                await message.answer(response.text)
                return
        except Exception as e:
            last_err = str(e)
            logging.error(f"Ошибка API: {last_err}")
            if "429" in last_err and total_keys > 1:
                current_key_idx = (current_key_idx + 1) % total_keys
                continue
            elif "503" in last_err:
                await asyncio.sleep(2)
                continue
            else:
                break

    await message.answer(f"Связь с чертогами нарушена: {last_err}")

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/healthz", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
