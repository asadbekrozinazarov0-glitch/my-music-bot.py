import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from threading import Thread

# --- SOZLAMALAR ---
TOKEN = "8986941580:AAEWeS5loRAE7kVnQo6IGlPH5ahtSGI5h-U"
ADMIN_ID = 5704733766
CHANNEL_ID = "@rznzrv_pg" 
WEBAPP_URL = "https://my-music-bot.onrender.com"  # Render havolangiz (keyin o'zgartirasiz)

bot = Bot(token=TOKEN)
dp = Dispatcher()

db_users = {ADMIN_ID: {"status": "approved", "name": "Admin"}}
db_musics = []
music_id_counter = 1

app = FastAPI()
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    
    if user_id == ADMIN_ID or db_users.get(user_id, {}).get("status") == "approved":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Mini Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
        await message.answer(
            "Salom! Botga xush kelibsiz. Musiqa yuborishingiz mumkin.",
            reply_markup=keyboard
        )
    else:
        db_users[user_id] = {"status": "pending", "name": user_name}
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")
            ]
        ])
        await bot.send_message(
            ADMIN_ID, 
            f"👤 Yangi foydalanuvchi botdan foydalanmoqchi:\n\nIsm: {user_name}\nID: {user_id}",
            reply_markup=admin_keyboard
        )
        await message.answer("Sizning so'rovingiz adminga yuborildi. Tasdiqlangach ishlaydi.")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    if user_id in db_users:
        db_users[user_id]["status"] = "approved"
        await bot.send_message(user_id, "✅ So'rovingiz tasdiqlandi! /start ni bosing.")
        await callback.message.edit_text(callback.message.text + "\n\nSTATUS: ✅ Tasdiqlandi")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    if user_id in db_users:
        db_users[user_id]["status"] = "rejected"
        await bot.send_message(user_id, "❌ So'rovingiz rad etildi.")
        await callback.message.edit_text(callback.message.text + "\n\nSTATUS: ❌ Rad etildi")

@dp.message(F.audio | F.document)
async def handle_music(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID and db_users.get(user_id, {}).get("status") != "approved":
        await message.answer("❌ Siz hali admin tomonidan tasdiqlanmagansiz.")
        return

    audio = message.audio or message.document
    if not audio:
        return

    file_id = audio.file_id
    performer = getattr(audio, "performer", None) or message.from_user.full_name
    title = getattr(audio, "title", None) or audio.file_name or "Noma'lum musiqa"
    
    global music_id_counter
    current_music_id = music_id_counter
    music_id_counter += 1

    caption = f"🎵 **{title}**\n🎤 Ijrochi: {performer}\n👤 Yuboruvchi: {message.from_user.full_name}\n#musiqa"
    
    sent_msg = None
    try:
        sent_msg = await bot.send_audio(
            chat_id=CHANNEL_ID,
            audio=file_id,
            caption=caption,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Kanalga yuborishda xatolik! Kanal ID to'g'riligini va bot kanalda admin ekanligini tekshiring.")
        return

    db_musics.append({
        "id": current_music_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "file_id": file_id,
        "performer": performer,
        "title": title,
        "message_id": sent_msg.message_id if sent_msg else None
    })

    await message.answer("✅ Musiqa kanalga va Mini Ilovaga qo'shildi!")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/musics")
async def get_musics(user_id: int):
    return JSONResponse(content={"musics": db_musics, "is_admin": user_id == ADMIN_ID})

@app.post("/api/delete")
async def delete_music(music_id: int = Form(...), user_id: int = Form(...)):
    global db_musics
    target_music = None
    for m in db_musics:
        if m["id"] == music_id:
            target_music = m
            break
            
    if not target_music:
        return {"success": False, "error": "Musiqa topilmadi"}

    if user_id != ADMIN_ID and target_music["user_id"] != user_id:
        return {"success": False, "error": "Huquq yo'q"}

    if target_music["message_id"]:
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=target_music["message_id"])
        except Exception as e:
            logging.error(f"O'chirishda xatolik: {e}")

    db_musics = [m for m in db_musics if m["id"] != music_id]
    return {"success": True}

async def main():
    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8000)
    
    t = Thread(target=run_fastapi, daemon=True)
    t.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  <!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Musiqalar Boshqaruvi</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; color: #333; }
        h1 { text-align: center; color: #2c3e50; }
        .music-card { background: #fff; padding: 15px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
        .music-info h4 { margin: 0 0 5px 0; color: #2980b9; }
        .music-info p { margin: 0; font-size: 14px; color: #7f8c8d; }
        button { background: #e74c3c; color: white; border: none; padding: 8px 12px; border-radius: 5px; cursor: pointer; }
        button:hover { background: #c0392b; }
    </style>
</head>
<body>
    <h1>Musiqalar Ro'yxati</h1>
    <div id="music-list">Yuklanmoqda...</div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const userId = tg.initDataUnsafe?.user?.id || 8986941580;

        async function loadMusics() {
            const response = await fetch(`/api/musics?user_id=${userId}`);
            const data = await response.json();
            const container = document.getElementById('music-list');
            container.innerHTML = '';

            if (data.musics.length === 0) {
                container.innerHTML = '<p style="text-align:center;">Hozircha musiqalar yo\'q.</p>';
                return;
            }

            data.musics.forEach(music => {
                const card = document.createElement('div');
                card.className = 'music-card';
                card.innerHTML = `
                    <div class="music-info">
                        <h4>${music.title}</h4>
                        <p>🎤 Ijrochi: ${music.performer}</p>
                        <p>👤 Yuboruvchi: ${music.user_name}</p>
                    </div>
                    <button onclick="deleteMusic(${music.id})">O'chirish</button>
                `;
                container.appendChild(card);
            });
        }

        async function deleteMusic(musicId) {
            if (!confirm("Bu musiqani kanaldan va ilovadan o'chirmoqchimisiz?")) return;

            const formData = new URLSearchParams();
            formData.append('music_id', musicId);
            formData.append('user_id', userId);

            const response = await fetch('/api/delete', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            if (result.success) {
                loadMusics();
            } else {
                alert("Xatolik: " + result.error);
            }
        }

        loadMusics();
    </script>
</body>
</html>
