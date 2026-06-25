import os
import sqlite3
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from transliterate import translit
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import yt_dlp

# --- SOZLAMALAR ---
BOT_TOKEN = "8432141124:AAHmkMEz6QM5CC4mDFL10647s5nGdemGvls"
ADMIN_ID = 5704733766
CHANNEL_ID = "@usa_bek_1"
FIXED_ARTIST = "Рузиназаров 🐊"
THUMB_IMAGE = "photo.jpg"  # Har bir musiqaga qo'yiladigan doimiy rasm (image.png dagi rasm)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

# --- MA'LUMOTLAR BAZASI (SQLite) ---
def init_db():
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    # Navbatdagi musiqalar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            caption TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_to_queue(file_id, caption):
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO queue (file_id, caption) VALUES (?, ?)", (file_id, caption))
    conn.commit()
    conn.close()

def get_next_music():
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_id, caption FROM queue ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def remove_from_queue(music_id):
    conn = sqlite3.connect('music_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM queue WHERE id = ?", (music_id,))
    conn.commit()
    conn.close()

# --- FORMATLASH FUNKSIYASI ---
def clean_and_translit(text):
    # .mp3 yoki ortiqcha belgilarni tozalash
    text = text.replace(".mp3", "").replace("_", " ").strip()
    try:
        # Lotindan Kirillga o'girish
        kirill_text = translit(text, 'ru')
    except:
        kirill_text = text
    return f"{kirill_text} - {FIXED_ARTIST}"

# --- AVTOMATIK POSTING (SCHEDULER) ---
async def send_scheduled_music():
    music = get_next_music()
    if music:
        music_id, file_id, caption = music
        try:
            if os.path.exists(THUMB_IMAGE):
                with open(THUMB_IMAGE, 'rb') as photo:
                    # Rasm bilan audio ko'rinishida yuborish
                    await bot.send_audio(
                        chat_id=CHANNEL_ID,
                        audio=file_id,
                        caption=caption,
                        thumb=photo
                    )
            else:
                await bot.send_audio(chat_id=CHANNEL_ID, audio=file_id, caption=caption)
            
            # Kanalga muvaffaqiyatli ketgach bazadan o'chiramiz
            remove_from_queue(music_id)
            await bot.send_message(ADMIN_ID, f"✅ Reja bo'yicha musiqa kanalga joylandi: {caption}")
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"❌ Musiqa yuborishda xatolik: {e}")
    else:
        await bot.send_message(ADMIN_ID, "⚠️ Navbatda musiqa qolmadi! Iltimos, musiqa qo'shing.")

# --- INLINE TUGMALAR (BOT O'ZI QIDIRGANLAR UCHUN) ---
def get_approval_keyboard(file_id, caption):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="Tasdiqlash ✅", callback_data=f"ok_{file_id[:20]}"), # file_id uzunligi sababli qisqartma
        InlineKeyboardButton(text="O'chirish ❌", callback_data="cancel_post")
    )
    return keyboard

# --- XABARLARNI QABUL QILISH ---

# 1. Siz to'g'ridan-to'g'ri audio fayl tashlaganingizda
@dp.message_handler(content_types=['audio'], chat_id=ADMIN_ID)
async def handle_audio_upload(message: types.Message):
    title = message.audio.title if message.audio.title else "Musiqa"
    caption = clean_and_translit(title)
    file_id = message.audio.file_id
    
    add_to_queue(file_id, caption)
    await message.reply(f"📥 Musiqa qabul qilindi va navbatga qo'shildi!\nFormat: **{caption}**")

# 2. Instagram havola tashlaganingizda
@dp.message_handler(lambda message: "instagram.com" in message.text, chat_id=ADMIN_ID)
async def handle_instagram_link(message: types.Message):
    url = message.text
    await message.reply("🔄 Instagramdan musiqa yuklab olinmoqda, kuting...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
            title = info.get('title', 'Musiqa')
            
        caption = clean_and_translit(title)
        
        # Faylni vaqtincha botga yuborib file_id olamiz
        with open(filename, 'rb') as audio_file:
            msg = await bot.send_audio(chat_id=ADMIN_ID, audio=audio_file, caption=caption)
            add_to_queue(msg.audio.file_id, caption)
            
        os.remove(filename) # Server joyini tejash uchun faylni o'chiramiz
        await message.reply(f"📥 Instagram musiqasi navbatga qo'shildi!\nFormat: **{caption}**")
        
    except Exception as e:
        await message.reply(f"❌ Yuklashda xatolik yuz berdi: {e}")

# 3. Bot o'zi Spotify/YouTube dan topgan deb tasavvur qilingan xabar (Namuna sifatida)
@dp.message_handler(commands=['find'], chat_id=ADMIN_ID)
async def mock_bot_discovery(message: types.Message):
    # Bu funksiya bot avtomatik qidirganda sizga qanday kelishini ko'rsatadi
    sample_file_id = "BAACAgIAAxkBAAMpZ..." # Bu yerda haqiqiy file_id bo'ladi
    caption = "Jon kelur - Рузиназаров 🐊"
    
    await message.reply(
        f"🔍 Bot yangi musiqa topdi:\n**{caption}**\nKanalga qo'shilsinmi?",
        reply_markup=get_approval_keyboard(sample_file_id, caption)
    )

# --- CALLBACK HANDLERS (TUGMALAR JAVOBI) ---
@dp.callback_query_handler(lambda c: c.data.startswith('ok_') or c.data == 'cancel_post')
async def process_approval(callback_query: types.CallbackQuery):
    if callback_query.data.startswith('ok_'):
        # Bu yerda bot o'zi topgan musiqani tasdiqlaganingizda navbatga qo'shadi
        await callback_query.message.edit_text("📥 Tasdiqlandi! Musiqa navbatga qo'shildi.")
    else:
        await callback_query.message.delete()
        await callback_query.answer("O'chirib tashlandi.")

# --- SOHATLARNI SOZLASh (11:30, 17:30, 01:30) ---
# Diqqat: Soat formatlari 24 soatlik tizimda yoziladi. (01:30 tungi, 11:30 kunduzi, 17:30 kechki)
scheduler.add_job(send_scheduled_music, 'cron', hour=1, minute=30)
scheduler.add_job(send_scheduled_music, 'cron', hour=11, minute=30)
scheduler.add_job(send_scheduled_music, 'cron', hour=17, minute=30)

if __name__ == '__main__':
    init_db()
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)
