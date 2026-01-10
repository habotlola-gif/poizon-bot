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
CHANNEL_ID = "@poizonlab2"

# Инициализация бота и БД
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# 🗄️ SQLite БАЗА ДАННЫХ (автоматически создается)
conn = sqlite3.connect('poizon_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц БД
cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price TEXT,
    photo TEXT,
    source TEXT,
    post_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    product TEXT,
    price TEXT,
    type TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Глобальные перемены
products_db = []
CHANNEL_POSTS = set()
PARSER_DELAY = 600  # 10 минут по умолчанию

def load_products():
    """Загрузка товаров из БД"""
    global products_db
    cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
    products_db = [{"id": row[0], **dict(zip(['name','description','price','photo','source','post_id'], row[1:]))} 
                   for row in cursor.fetchall()]
    return products_db

def save_order(order_data):
    """Сохранение заказа в БД"""
    cursor.execute('''
    INSERT INTO orders (user_id, username, full_name, product, price, type)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (order_data['user_id'], order_data['username'], order_data['full_name'], 
          order_data['product'], order_data['price'], order_data['type']))
    conn.commit()

def format_price(price: str) -> str:
    """Форматирование цены"""
    return re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1 ', price.replace(' ', ''))

load_products()  # Загружаем товары при старте

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🔗 Заказ по ссылке", callback_data="order_link")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

def admin_menu():
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔄 Парсер канала", callback_data="parse_channel")],
        [InlineKeyboardButton(text=f"⏱ Delay: {PARSER_DELAY}s", callback_data="admin_delay")],
        [InlineKeyboardButton(text="◀️ Главное", callback_data="back_main")]
    ])

# ===== АВТО-ПАРСЕР @poizonlab2 =====
async def parse_poizonlab_channel():
    """Парсит @poizonlab2 и добавляет товары в БД"""
    global CHANNEL_POSTS
    
    try:
        messages = await bot.get_chat_history(CHANNEL_ID, limit=20)
        new_products = 0
        
        for message in reversed(messages):
            if message.message_id in CHANNEL_POSTS:
                continue
                
            if not (message.photo or message.caption):
                continue
            
            text = (message.caption or message.text or "").lower()
            
            # 🔍 Поиск цены (4653, 4 653, 4653₽, 4653руб)
            price_match = re.search(r'(\d[\d\s]*?)(?=\s*(?:₽|руб|r|u|b|\*|№|$))', text)
            price = format_price(price_match.group(1)) if price_match else "Цена ДМ"
            
            # 📝 Название товара
            title = re.sub(r'цена.*?₽.*', '', text)[:80].strip()
            if len(title) < 10:
                title = f"POIZON LAB #{message.message_id}"
            
            # 💾 Сохраняем в БД (НЕ дублируем)
            cursor.execute('''
            INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, text[:300], price, 
                  message.photo[-1].file_id if message.photo else None,
                  'poizonlab2', message.message_id))
            
            CHANNEL_POSTS.add(message.message_id)
            new_products += cursor.rowcount
        
        conn.commit()
        load_products()
        
        if new_products > 0:
            await bot.send_message(ADMIN_ID, 
                f"🆕 **Парсер @poizonlab2**\\n\\n"
                f"✅ Добавлено **{new_products}** новых товаров!",
                parse_mode="Markdown")
            print(f"✅ +{new_products} товаров из канала")
            
    except Exception as e:
        print(f"❌ Парсер: {e}")

async def auto_parse_channel():
    """Авто-парсинг каждые PARSER_DELAY секунд"""
    global PARSER_DELAY
    print(f"🔄 Авто-парсер запущен: каждые {PARSER_DELAY} сек")
    while True:
        await parse_poizonlab_channel()
        await asyncio.sleep(PARSER_DELAY)

# ===== КОМАНДЫ =====
@router.message(Command("start"))
async def cmd_start(message: Message):
    stats = len(products_db)
    await message.answer(
        f"👋 **POIZON LAB Bot**\\n\\n"
        f"🛍 **Авто-каталог** из @poizonlab2\\n"
        f"📦 Товаров: **{stats}**\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    
    await message.answer(
        f"🔐 **Админ-панель**\\n\\n"
        f"📦 Товаров: {len(products_db)}\\n"
        f"🆕 Новых заказов: {new_orders}\\n"
        f"⏱ Парсер: {PARSER_DELAY}с",
        reply_markup=admin_menu(), parse_mode="Markdown"
    )

@router.message(Command("delay"))
async def cmd_delay(message: Message):
    """Настройка интервала парсера"""
    global PARSER_DELAY
    
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Только админ!")
    
    try:
        new_delay = int(message.text.split(maxsplit=1)[1])
        if new_delay < 30:
            return await message.answer("❌ Минимум 30 секунд!")
        
        PARSER_DELAY = new_delay
        await message.answer(
            f"✅ **Интервал изменен!**\\n\\n"
            f"⏱ **{PARSER_DELAY} сек** ({PARSER_DELAY//60} мин)",
            parse_mode="Markdown"
        )
        print(f"⏱ Интервал: {PARSER_DELAY}с")
        
    except (IndexError, ValueError):
        await message.answer(
            f"📊 **Текущий интервал:** {PARSER_DELAY}с\\n\\n"
            f"**Примеры:**\\n"
            f"`/delay 60` — 1 минута\\n"
            f"`/delay 300` — 5 минут\\n"
            f"`/delay 1800` — 30 минут",
            parse_mode="Markdown"
        )

# ===== КАТАЛОГ =====
@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            "📦 **Каталог пуст**\\n\\n"
            "🔄 Ожидаем посты из @poizonlab2...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить канал", callback_data="parse_channel")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
            ]), parse_mode="Markdown"
        )
        return
    
    text = f"📦 **Каталог** ({len(products_db)} товаров)\\n\\n"
    keyboard = []
    
    for product in products_db[:10]:
        keyboard.append([InlineKeyboardButton(
            text=f"{format_price(product['price'])} | {product['name'][:25]}",
            callback_data=f"product_{product['id']}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="parse_channel")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    product = next((p for p in products_db if p['id'] == pid), None)
    
    if not product:
        return await callback.answer("❌ Товар не найден")
    
    text = f"🛍 **{product['name']}**\\n\\n{product['description']}\\n\\n💰 **{format_price(product['price'])}**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="◀️ Каталог", callback_data="catalog")]
    ])
    
    if product.get('photo'):
        await callback.message.delete()
        await bot.send_photo(callback.from_user.id, product['photo'], caption=text, 
                           reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    product = next((p for p in products_db if p['id'] == pid), None)
    
    order_data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "no_username",
        'full_name': callback.from_user.full_name,
        'product': product['name'],
        'price': product['price'],
        'type': 'catalog'
    }
    
    save_order(order_data)
    
    await bot.send_message(ADMIN_ID, 
        f"🔔 **НОВЫЙ ЗАКАЗ #{cursor.lastrowid}!**\\n\\n"
        f"👤 {order_data['full_name']} (@{order_data['username']})\\n"
        f"🛍 **{product['name']}**\\n"
        f"💰 {format_price(product['price'])}\\n"
        f"🆔 `{order_data['user_id']}`",
        parse_mode="Markdown"
    )
    
    await callback.message.edit_text(
        f"✅ **Заказ #{cursor.lastrowid} принят!**\\n\\n"
        f"🛍 {product['name']}\\n"
        f"💰 {format_price(product['price'])}\\n\\n"
        f"⏳ Менеджер свяжется!",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

# ===== АДМИН ПАНЕЛЬ =====
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        f"📊 **Статистика**\\n\\n"
        f"📦 Товаров: {len(products_db)}\\n"
        f"🛒 Всего заказов: {total_orders}\\n"
        f"🆕 Новых: {new_orders}\\n"
        f"⏱ Парсер: {PARSER_DELAY}с\\n\\n"
        f"🗄️ **База:** poizon_bot.db",
        reply_markup=admin_menu(), parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10")
    orders = cursor.fetchall()
    
    if not orders:
        return await callback.message.edit_text("📦 Заказов нет", reply_markup=admin_menu())
    
    text = "📦 **Последние заказы:**\\n\\n"
    for order in orders:
        text += f"🆔 #{order[0]} | @{order[2]} | {order[4][:30]} | {order[5]}\n"
    
    await callback.message.edit_text(text, reply_markup=admin_menu(), parse_mode="Markdown")

@router.callback_query(F.data == "parse_channel")
async def manual_parse(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await parse_poizonlab_channel()
    await callback.answer("🔄 Канал обновлен!")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_menu())

# ===== ЗАПУСК =====
async def main():
    dp.include_router(router)
    
    # 🎯 АВТО-ПАРСЕР КАНАЛА
    asyncio.create_task(auto_parse_channel())
    
    print("🤖 POIZON LAB Bot запущен!")
    print(f"📱 Парсит: {CHANNEL_ID}")
    print(f"⏱ Интервал: {PARSER_DELAY}с")
    print(f"🗄️ База: poizon_bot.db")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
