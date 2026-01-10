import os
import asyncio
import re
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = "@asdasdadsads123312"  # ✅ НОВЫЙ КАНАЛ

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# 🗄️ БАЗА ДАННЫХ
conn = sqlite3.connect('poizon_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    price TEXT,
    photo TEXT,
    source TEXT,
    post_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    product TEXT,
    price TEXT,
    type TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()

products_db = []
CHANNEL_POSTS = set()
PARSER_DELAY = 600

def load_products():
    global products_db
    cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
    products_db = [{"id": row[0], **dict(zip(['name','description','price','photo','source','post_id'], row[1:]))} for row in cursor.fetchall()]
    return products_db

def save_order(order_data):
    cursor.execute('INSERT INTO orders (user_id, username, full_name, product, price, type) VALUES (?, ?, ?, ?, ?, ?)', 
                   (order_data['user_id'], order_data['username'], order_data['full_name'], order_data['product'], order_data['price'], order_data['type']))
    conn.commit()

def format_price(price):
    return re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1 ', price.replace(' ', ''))

load_products()

# Клавиатуры
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="Заказ по ссылке", callback_data="order_link")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ])

def admin_menu():
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔄 Парсер канала", callback_data="parse_channel")],
        [InlineKeyboardButton(text=f"⏱ {PARSER_DELAY}s", callback_data="admin_delay")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])

# 🔥 ПАРСЕР КАНАЛА (ИСПРАВЛЕН)
async def parse_channel():
    global CHANNEL_POSTS
    try:
        messages = await bot.get_chat_history(CHANNEL_ID, limit=20)
        new_count = 0
        
        for message in reversed(messages):
            if message.message_id in CHANNEL_POSTS:
                continue
            
            if not message.photo:
                continue
            
            text = message.caption or message.text or ""
            
            # Цена
            price_match = re.search(r'(\d[\d\s]*?)(?=\s*[₽руб$])', text)
            price = format_price(price_match.group(1)) if price_match else "Цена ДМ"
            
            # Название
            title = text.split('\n')[0][:60] if text else f"Товар #{message.message_id}"
            
            # ✅ САЙТ В БД БЕЗ \n
            cursor.execute('''
            INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, text[:250], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id))
            
            if cursor.rowcount > 0:
                new_count += 1
            
            CHANNEL_POSTS.add(message.message_id)
        
        conn.commit()
        load_products()
        
        if new_count > 0:
            await bot.send_message(ADMIN_ID, f"✅ +{new_count} товаров из {CHANNEL_ID}")
        
        print(f"Парсер: +{new_count} товаров")
        
    except Exception as e:
        print(f"Парсер ошибка: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Парсер: {CHANNEL_ID} недоступен")

async def auto_parser():
    global PARSER_DELAY
    while True:
        await parse_channel()
        await asyncio.sleep(PARSER_DELAY)

# Команды
@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        f"POIZON LAB\\n\\n"
        f"Авто-каталог: {CHANNEL_ID}\\n"
        f"Товаров: {len(products_db)}\\n\\n"
        "Выберите:",
        reply_markup=main_menu(), parse_mode="MarkdownV2"
    )

@router.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    await message.answer(
        f"Админ-панель\\n\\n"
        f"Товаров: {len(products_db)}\\n"
        f"Новых заказов: {new_orders}\\n"
        f"Парсер: {PARSER_DELAY}с\\n"
        f"Канал: {CHANNEL_ID}",
        reply_markup=admin_menu(), parse_mode="MarkdownV2"
    )

@router.message(Command("delay"))
async def delay(message: Message):
    global PARSER_DELAY
    if message.from_user.id != ADMIN_ID: return
    
    try:
        new_delay = int(message.text.split()[1])
        if new_delay < 30: raise ValueError()
        PARSER_DELAY = new_delay
        await message.answer(f"✅ Интервал: {new_delay}с ({new_delay//60}м)")
    except:
        await message.answer(
            f"Текущий: {PARSER_DELAY}с\\n\\n"
            "/delay 60  — 1 минута\\n"
            "/delay 300 — 5 минут",
            parse_mode="MarkdownV2"
        )

# Каталог
@router.callback_query(F.data == "catalog")
async def catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            "Каталог пуст\\n\\n🔄 Ожидаем посты...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить канал", callback_data="parse_channel")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
            ]), parse_mode="MarkdownV2"
        )
        return
    
    text = f"Каталог ({len(products_db)} шт)\\n\\n"
    kb = []
    for p in products_db[:10]:
        kb.append([InlineKeyboardButton(text=f"{format_price(p['price'])} | {p['name'][:25]}", callback_data=f"product_{p['id']}")])
    kb.extend([[InlineKeyboardButton(text="🔄 Обновить", callback_data="parse_channel")], [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="MarkdownV2")

@router.callback_query(F.data.startswith("product_"))
async def product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    if not p: return await callback.answer("❌ Товар удален")
    
    text = f"{p['name']}\\n\\n{p['description']}\\n\\n💰 <b>{format_price(p['price'])}</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="◀️ Каталог", callback_data="catalog")]
    ])
    
    try:
        if p['photo']:
            await callback.message.delete()
            await bot.send_photo(callback.from_user.id, p['photo'], caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text("❌ Ошибка фото", reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    
    order_data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "none",
        'full_name': callback.from_user.full_name,
        'product': p['name'],
        'price': p['price'],
        'type': 'catalog'
    }
    
    save_order(order_data)
    
    await bot.send_message(ADMIN_ID, 
        f"🔔 НОВЫЙ ЗАКАЗ #{cursor.lastrowid}!\\n"
        f"👤 {order_data['full_name']} (@{order_data['username']})\\n"
        f"🛍 {p['name']}\\n💰 {format_price(p['price'])}\\n🆔 {order_data['user_id']}",
        parse_mode="MarkdownV2"
    )
    
    await callback.message.edit_text(
        f"✅ Заказ #{cursor.lastrowid} принят!\\n"
        f"🛍 {p['name']}\\n💰 {format_price(p['price'])}\\n⏳ Ждите связи!",
        reply_markup=main_menu(), parse_mode="MarkdownV2"
    )

# Админ
@router.callback_query(F.data.in_(["admin_stats", "admin_orders", "parse_channel", "back_main"]))
async def admin_callbacks(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return await callback.answer()
    
    if callback.data == "admin_stats":
        cursor.execute("SELECT COUNT(*) FROM orders")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
        new_o = cursor.fetchone()[0]
        await callback.message.edit_text(
            f"📊 Статистика:\\n\\nТоваров: {len(products_db)}\\nЗаказов всего: {total}\\nНовых: {new_o}\\nПарсер: {PARSER_DELAY}с",
            reply_markup=admin_menu(), parse_mode="MarkdownV2"
        )
    
    elif callback.data == "admin_orders":
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
        orders = cursor.fetchall()
        if not orders:
            return await callback.message.edit_text("Заказов нет", reply_markup=admin_menu())
        text = "📦 Заказы:\n\n"
        for o in orders:
            text += f"#{o[0]} | @{o[2]} | {o[4][:25]} | {o[5]}\n"
        await callback.message.edit_text(text, reply_markup=admin_menu(), parse_mode="MarkdownV2")
    
    elif callback.data == "parse_channel":
        await parse_channel()
        await callback.answer("🔄 Обновлено!")
    
    elif callback.data == "back_main":
        await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_menu())

async def main():
    dp.include_router(router)
    asyncio.create_task(auto_parser())
    print(f"🤖 Запущен! Канал: {CHANNEL_ID} | Delay: {PARSER_DELAY}s")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
