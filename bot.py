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

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = "@asdasdadsads123312"  # Ваш канал

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# ===== БАЗА ДАННЫХ =====
conn = sqlite3.connect('poizon_bot.db', check_same_thread=False)
cursor = conn.cursor()

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

# Глобальные переменные
products_db = []

# ===== ФУНКЦИИ БД =====
def load_products():
    """Загрузка товаров из БД"""
    global products_db
    cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
    products_db = []
    for row in cursor.fetchall():
        products_db.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3],
            'photo': row[4],
            'source': row[5],
            'post_id': row[6]
        })
    return products_db

def save_order(order_data):
    """Сохранение заказа"""
    cursor.execute('''
    INSERT INTO orders (user_id, username, full_name, product, price, type)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (order_data['user_id'], order_data['username'], order_data['full_name'],
          order_data['product'], order_data['price'], order_data['type']))
    conn.commit()
    return cursor.lastrowid

def format_price(price):
    """Форматирование цены"""
    price_str = str(price).replace(' ', '')
    return re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1 ', price_str)

load_products()

# ===== СОСТОЯНИЯ FSM =====
class OrderLink(StatesGroup):
    waiting_for_link = State()
    waiting_for_size = State()
    waiting_for_comment = State()

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🔗 Заказ по ссылке", callback_data="order_link")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

# ===== АВТОМАТИЧЕСКИЙ ПАРСЕР КАНАЛА =====
@router.channel_post()
async def auto_parse_channel_post(message: Message):
    """Автоматически ловит КАЖДЫЙ новый пост из канала"""
    
    # Проверка что это нужный канал
    try:
        channel_username = message.chat.username
        if not channel_username or f"@{channel_username}" != CHANNEL_ID:
            return
    except:
        return
    
    print(f"📱 Новый пост в канале #{message.message_id}")
    
    # Должно быть фото
    if not message.photo:
        print("⚠️ Пост без фото - пропускаем")
        return
    
    text = message.caption or ""
    
    # Ищем цену (разные форматы: 4653₽, 4 653 руб, 4653)
    price_match = re.search(r'(\d[\d\s]*?)(?=\s*[₽руб$RUB])', text)
    if price_match:
        price = price_match.group(1).replace(' ', '')
    else:
        # Пробуем найти просто число
        price_match = re.search(r'(\d{3,})', text)
        price = price_match.group(1) if price_match else "Цена в ЛС"
    
    # Название (первая строка или первые 60 символов)
    lines = text.split('\n')
    if lines and len(lines[0]) > 5:
        title = lines[0][:60].strip()
    else:
        title = text[:60].strip() if text else f"Товар #{message.message_id}"
    
    # Сохраняем в БД (НЕ дублируем)
    try:
        cursor.execute('''
        INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, text[:300], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id))
        
        conn.commit()
        
        # Если добавлен новый товар
        if cursor.rowcount > 0:
            load_products()
            
            # Уведомление админу
            await bot.send_message(
                ADMIN_ID,
                f"✅ НОВЫЙ ТОВАР В КАТАЛОГЕ!\n\n"
                f"🛍 {title}\n"
                f"💰 {format_price(price)} ₽\n\n"
                f"📦 Всего товаров: {len(products_db)}"
            )
            
            print(f"✅ Товар добавлен: {title} | {price}₽")
        else:
            print(f"⚠️ Товар уже существует: #{message.message_id}")
    
    except Exception as e:
        print(f"❌ Ошибка сохранения товара: {e}")

# ===== КОМАНДЫ =====
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Добро пожаловать в POIZON LAB!\n\n"
        f"📦 Товаров в каталоге: {len(products_db)}\n"
        f"🔄 Автоматический каталог из {CHANNEL_ID}\n\n"
        f"Выберите действие:",
        reply_markup=main_menu()
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    
    await message.answer(
        f"🔐 Админ-панель POIZON LAB\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🛒 Заказов всего: {total_orders}\n"
        f"🆕 Новых заказов: {new_orders}\n"
        f"📱 Канал: {CHANNEL_ID}\n"
        f"🔄 Парсер: Автоматический (мгновенно)\n\n"
        f"💡 Новые посты в канале добавляются автоматически!",
        reply_markup=admin_menu()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Помощь по боту\n\n"
        "Команды:\n"
        "/start - Главное меню\n"
        "/catalog - Каталог товаров\n"
        "/help - Эта справка\n\n"
        "Для админа:\n"
        "/admin - Админ-панель",
        reply_markup=back_button()
    )

@router.message(Command("catalog"))
async def cmd_catalog(message: Message):
    if not products_db:
        await message.answer(
            f"📦 Каталог пока пуст\n\n"
            f"Ожидаем посты из {CHANNEL_ID}...",
            reply_markup=back_button()
        )
        return
    
    text = f"📦 Каталог POIZON LAB\n\nВсего товаров: {len(products_db)}\n\n"
    keyboard = []
    
    for product in products_db[:10]:
        button_text = f"{format_price(product['price'])} ₽ | {product['name'][:25]}"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"product_{product['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# ===== КАТАЛОГ =====
@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            f"📦 Каталог пока пуст\n\n"
            f"🔄 Ожидаем посты из {CHANNEL_ID}...\n\n"
            f"💡 Новые товары появятся автоматически!",
            reply_markup=back_button()
        )
        return
    
    text = f"📦 Каталог POIZON LAB\n\nВсего товаров: {len(products_db)}\n\n"
    keyboard = []
    
    for product in products_db[:10]:
        button_text = f"{format_price(product['price'])} ₽ | {product['name'][:25]}"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"product_{product['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = next((p for p in products_db if p['id'] == product_id), None)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    text = (
        f"🛍 {product['name']}\n\n"
        f"{product['description']}\n\n"
        f"💰 Цена: {format_price(product['price'])} ₽"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data=f"buy_{product_id}")],
        [InlineKeyboardButton(text="◀️ К каталогу", callback_data="catalog")]
    ])
    
    try:
        if product['photo']:
            await callback.message.delete()
            await bot.send_photo(
                callback.from_user.id,
                photo=product['photo'],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = next((p for p in products_db if p['id'] == product_id), None)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    order_data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "no_username",
        'full_name': callback.from_user.full_name,
        'product': product['name'],
        'price': product['price'],
        'type': 'catalog'
    }
    
    order_id = save_order(order_data)
    
    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🔔 НОВЫЙ ЗАКАЗ #{order_id}\n\n"
        f"👤 Клиент: {order_data['full_name']}\n"
        f"📱 Username: @{order_data['username']}\n"
        f"🆔 User ID: {order_data['user_id']}\n\n"
        f"🛍 Товар: {product['name']}\n"
        f"💰 Цена: {format_price(product['price'])} ₽"
    )
    
    # Подтверждение пользователю
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} принят!\n\n"
        f"🛍 {product['name']}\n"
        f"💰 {format_price(product['price'])} ₽\n\n"
        f"⏳ Скоро с вами свяжется менеджер!\n"
        f"Ожидайте сообщения.",
        reply_markup=main_menu()
    )
    await callback.answer("✅ Заказ оформлен!")

# ===== ЗАКАЗ ПО ССЫЛКЕ =====
@router.callback_query(F.data == "order_link")
async def start_order_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 Заказ по ссылке\n\n"
        "Отправьте ссылку на товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")]
        ])
    )
    await state.set_state(OrderLink.waiting_for_link)

@router.message(OrderLink.waiting_for_link)
async def process_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("📏 Укажите размер:")
    await state.set_state(OrderLink.waiting_for_size)

@router.message(OrderLink.waiting_for_size)
async def process_size(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("💬 Добавьте комментарий:")
    await state.set_state(OrderLink.waiting_for_comment)

@router.message(OrderLink.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    
    order_data = {
        'user_id': message.from_user.id,
        'username': message.from_user.username or "no_username",
        'full_name': message.from_user.full_name,
        'product': f"Заказ по ссылке (размер {data['size']})",
        'price': "Уточняется",
        'type': 'link'
    }
    
    order_id = save_order(order_data)
    
    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🔔 НОВЫЙ ЗАКАЗ ПО ССЫЛКЕ #{order_id}\n\n"
        f"👤 {order_data['full_name']}\n"
        f"📱 @{order_data['username']}\n"
        f"🆔 {order_data['user_id']}\n\n"
        f"🔗 {data['link']}\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 {message.text}"
    )
    
    await message.answer(
        f"✅ Заказ #{order_id} принят!\n\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 Комментарий: {message.text}\n\n"
        f"⏳ Менеджер рассчитает стоимость!",
        reply_markup=main_menu()
    )
    await state.clear()

# ===== ПОДДЕРЖКА =====
@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    try:
        admin_chat = await bot.get_chat(ADMIN_ID)
        admin_username = admin_chat.username if admin_chat.username else "admin"
    except:
        admin_username = "admin"
    
    await callback.message.edit_text(
        f"💬 Техподдержка\n\n"
        f"📞 Менеджер: @{admin_username}\n"
        f"⏰ Время работы: 24/7\n"
        f"⚡️ Ответ в течение 5 минут",
        reply_markup=back_button()
    )

# ===== АДМИН ПАНЕЛЬ =====
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new_orders = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        f"📊 Статистика POIZON LAB\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🛒 Всего заказов: {total_orders}\n"
        f"🆕 Новых: {new_orders}\n"
        f"📱 Канал: {CHANNEL_ID}\n"
        f"🔄 Парсер: Автоматический\n\n"
        f"🗄️ База: poizon_bot.db",
        reply_markup=admin_menu()
    )

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10")
    orders = cursor.fetchall()
    
    if not orders:
        await callback.message.edit_text(
            "📦 Заказов пока нет",
            reply_markup=admin_menu()
        )
        return
    
    text = "📦 Последние 10 заказов:\n\n"
    for order in orders:
        text += (
            f"🆔 #{order[0]} | @{order[2]}\n"
            f"   {order[4][:40]}\n"
            f"   💰 {order[5]} | {order[7]}\n\n"
        )
    
    await callback.message.edit_text(text, reply_markup=admin_menu())

# ===== НАВИГАЦИЯ =====
@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 Главное меню\n\nВыберите действие:",
        reply_markup=main_menu()
    )

# ===== ЗАПУСК БОТА =====
async def main():
    dp.include_router(router)
    
    print("=" * 60)
    print("🤖 POIZON LAB БОТ ЗАПУЩЕН!")
    print(f"📱 Канал: {CHANNEL_ID}")
    print(f"📦 Товаров в базе: {len(products_db)}")
    print(f"🔄 Парсер: АВТОМАТИЧЕСКИЙ (мгновенно)")
    print(f"🗄️ База данных: poizon_bot.db")
    print("=" * 60)
    print("\n💡 Новые посты в канале автоматически добавляются в каталог!\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
