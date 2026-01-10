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
CHANNEL_ID = "@asdasdadsads123312"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# ===== КАТЕГОРИИ (БЕЗ БРЕНДОВ) =====
CATEGORIES = {
    '👟 Обувь': ['кроссовки', 'кросс', 'ботинки', 'тапки', 'сланцы', 'slides', 'туфли', 'boots', 'sneakers', 'air force', 'dunk'],
    '🧥 Верхняя одежда': ['куртка', 'пуховик', 'пальто', 'парка', 'ветровка', 'бомбер', 'jacket', 'coat', 'hoodie', 'худи', 'толстовка', 'свитшот', 'кофта'],
    '👕 Одежда': ['футболка', 'майка', 'шорты', 'джинсы', 'брюки', 'штаны', 'рубашка', 'shirt', 'pants', 'jeans', 'tshirt', 'tee', 'polo', 'свитер'],
    '👜 Сумки': ['сумка', 'рюкзак', 'сумочка', 'клатч', 'кошелек', 'портмоне', 'bag', 'backpack', 'wallet', 'crossbody', 'messenger', 'поясная'],
    '⌚️ Аксессуары': ['часы', 'браслет', 'цепь', 'кольцо', 'серьги', 'очки', 'кепка', 'шапка', 'перчатки', 'ремень', 'носки', 'watch', 'belt', 'cap', 'hat', 'glasses', 'chain', 'подвеска'],
    '💄 Косметика': ['крем', 'помада', 'тушь', 'духи', 'парфюм', 'маска', 'сыворотка', 'тональ', 'пудра', 'лак', 'лосьон', 'косметика', 'perfume', 'cream', 'serum', 'lipstick', 'блеск'],
    '🎒 Другое': []
}

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
    category TEXT DEFAULT '🎒 Другое',
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

products_db = []

# ===== ФУНКЦИИ =====
def detect_category(text):
    """Автоопределение категории с приоритетом"""
    text_lower = text.lower()
    
    # ПРИОРИТЕТ 1: Верхняя одежда (проверяем ПЕРВОЙ)
    for keyword in ['худи', 'hoodie', 'толстовка', 'свитшот', 'куртка', 'пуховик', 'пальто', 'парка', 'ветровка', 'бомбер', 'jacket', 'coat', 'кофта']:
        if keyword in text_lower:
            return '🧥 Верхняя одежда'
    
    # ПРИОРИТЕТ 2: Одежда
    for keyword in ['футболка', 'майка', 'шорты', 'джинсы', 'брюки', 'штаны', 'рубашка', 'shirt', 'pants', 'jeans', 'tshirt', 'tee', 'polo', 'свитер']:
        if keyword in text_lower:
            return '👕 Одежда'
    
    # ПРИОРИТЕТ 3: Обувь
    for keyword in ['кроссовки', 'кросс', 'ботинки', 'тапки', 'сланцы', 'slides', 'туфли', 'boots', 'sneakers', 'air force', 'dunk']:
        if keyword in text_lower:
            return '👟 Обувь'
    
    # ПРИОРИТЕТ 4: Сумки
    for keyword in ['сумка', 'рюкзак', 'сумочка', 'клатч', 'кошелек', 'портмоне', 'bag', 'backpack', 'wallet', 'crossbody', 'messenger', 'поясная']:
        if keyword in text_lower:
            return '👜 Сумки'
    
    # ПРИОРИТЕТ 5: Аксессуары
    for keyword in ['часы', 'браслет', 'цепь', 'кольцо', 'серьги', 'очки', 'кепка', 'шапка', 'перчатки', 'ремень', 'носки', 'watch', 'belt', 'cap', 'hat', 'glasses', 'chain', 'подвеска']:
        if keyword in text_lower:
            return '⌚️ Аксессуары'
    
    # ПРИОРИТЕТ 6: Косметика
    for keyword in ['крем', 'помада', 'тушь', 'духи', 'парфюм', 'маска', 'сыворотка', 'тональ', 'пудра', 'лак', 'лосьон', 'косметика', 'perfume', 'cream', 'serum', 'lipstick', 'блеск']:
        if keyword in text_lower:
            return '💄 Косметика'
    
    return '🎒 Другое'

def load_products():
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
            'post_id': row[6],
            'category': row[7] if len(row) > 7 else '🎒 Другое'
        })
    return products_db

def save_order(order_data):
    cursor.execute('''INSERT INTO orders (user_id, username, full_name, product, price, type)
    VALUES (?, ?, ?, ?, ?, ?)''', (order_data['user_id'], order_data['username'], 
    order_data['full_name'], order_data['product'], order_data['price'], order_data['type']))
    conn.commit()
    return cursor.lastrowid

def format_price(price):
    price_str = str(price).replace(' ', '')
    return re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1 ', price_str)

load_products()

# ===== FSM =====
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
        [InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products")],
        [InlineKeyboardButton(text="🛒 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Главное", callback_data="back_main")]
    ])

def catalog_categories():
    """Категории каталога"""
    kb = []
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        if count > 0:
            kb.append([InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"cat_{cat}")])
    kb.append([InlineKeyboardButton(text="📦 Все товары", callback_data="cat_all")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def paginate_products(products, page=0, category='all'):
    """Пагинация товаров"""
    per_page = 8
    start = page * per_page
    end = start + per_page
    
    filtered = [p for p in products if category == 'all' or p.get('category') == category]
    page_products = filtered[start:end]
    
    kb = []
    for p in page_products:
        kb.append([InlineKeyboardButton(
            text=f"{format_price(p['price'])} ₽ | {p['name'][:30]}",
            callback_data=f"product_{p['id']}"
        )])
    
    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{category}_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{(len(filtered)-1)//per_page+1}", callback_data="pageinfo"))
    if end < len(filtered):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{category}_{page+1}"))
    
    if nav:
        kb.append(nav)
    
    kb.append([InlineKeyboardButton(text="🔙 Категории", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=kb), len(filtered)

# ===== ПАРСЕР =====
@router.channel_post()
async def auto_parse(message: Message):
    try:
        channel_username = message.chat.username
        if not channel_username or f"@{channel_username}" != CHANNEL_ID:
            return
    except:
        return
    
    if not message.photo:
        return
    
    text = message.caption or ""
    
    # Парсинг цены
    price = "Цена в ЛС"
    
    # Вариант 1: Цена с символами (4653₽, 4 653 руб)
    match1 = re.search(r'(\d[\d\s]+?)\s*[₽руб$RUB]', text, re.IGNORECASE)
    if match1:
        price = match1.group(1).replace(' ', '')
    else:
        # Вариант 2: "Цена: 5000"
        match2 = re.search(r'цена[\s\-:]+(\d[\d\s]+)', text, re.IGNORECASE)
        if match2:
            price = match2.group(1).replace(' ', '')
        else:
            # Вариант 3: Просто число
            match3 = re.search(r'\b(\d{3,})\b', text)
            if match3:
                price = match3.group(1)
    
    # Название
    lines = text.split('\n')
    title = lines[0][:60].strip() if lines and len(lines[0]) > 5 else text[:60].strip() or f"Товар #{message.message_id}"
    
    # Категория (с приоритетом)
    category = detect_category(text)
    
    try:
        cursor.execute('''INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)''', (title, text[:300], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id, category))
        conn.commit()
        
        if cursor.rowcount > 0:
            load_products()
            await bot.send_message(ADMIN_ID,
                f"✅ НОВЫЙ ТОВАР!\n\n{category}\n🛍 {title}\n💰 {format_price(price)} ₽\n\n📦 Всего: {len(products_db)}")
            print(f"✅ {category} | {title} | {price}₽")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# ===== КОМАНДЫ =====
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Добро пожаловать в POIZON LAB!\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🔄 Автокаталог: {CHANNEL_ID}\n\n"
        f"Выберите действие:",
        reply_markup=main_menu()
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new = cursor.fetchone()[0]
    await message.answer(
        f"🔐 Админ-панель POIZON LAB\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🆕 Новых заказов: {new}",
        reply_markup=admin_menu()
    )

# ===== КАТАЛОГ =====
@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            f"📦 Каталог пуст\n\n🔄 Ждем посты из {CHANNEL_ID}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
            ])
        )
        return
    
    await callback.message.edit_text(
        f"📦 Каталог POIZON LAB\n\n"
        f"Всего товаров: {len(products_db)}\n\n"
        f"Выберите категорию:",
        reply_markup=catalog_categories()
    )

@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    kb, total = paginate_products(products_db, 0, category)
    
    cat_name = category if category != 'all' else 'Все товары'
    await callback.message.edit_text(
        f"📦 {cat_name}\n\nТоваров: {total}",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("page_"))
async def paginate(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[-1])
    category = "_".join(parts[1:-1])
    
    kb, total = paginate_products(products_db, page, category)
    
    cat_name = category if category != 'all' else 'Все товары'
    await callback.message.edit_text(
        f"📦 {cat_name}\n\nТоваров: {total}",
        reply_markup=kb
    )

@router.callback_query(F.data == "pageinfo")
async def pageinfo(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    
    if not p:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    text = f"🛍 {p['name']}\n\n{p['description']}\n\n💰 Цена: {format_price(p['price'])} ₽\n\n📁 {p.get('category', '🎒 Другое')}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="◀️ Каталог", callback_data="catalog")]
    ])
    
    try:
        if p['photo']:
            await callback.message.delete()
            await bot.send_photo(callback.from_user.id, p['photo'], caption=text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)
    except:
        await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    
    if not p:
        await callback.answer("❌ Товар удален", show_alert=True)
        return
    
    order_data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "no_username",
        'full_name': callback.from_user.full_name,
        'product': p['name'],
        'price': p['price'],
        'type': 'catalog'
    }
    
    order_id = save_order(order_data)
    
    await bot.send_message(ADMIN_ID,
        f"🔔 НОВЫЙ ЗАКАЗ #{order_id}\n\n"
        f"👤 {order_data['full_name']}\n"
        f"📱 @{order_data['username']}\n"
        f"🆔 {order_data['user_id']}\n\n"
        f"🛍 {p['name']}\n"
        f"💰 {format_price(p['price'])} ₽")
    
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} принят!\n\n"
        f"🛍 {p['name']}\n"
        f"💰 {format_price(p['price'])} ₽\n\n"
        f"⏳ Скоро с вами свяжется менеджер!",
        reply_markup=main_menu()
    )

# ===== АДМИН УПРАВЛЕНИЕ =====
@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    kb = []
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        kb.append([InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"admincat_{cat}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(
        "📦 Управление товарами\n\nВыберите категорию для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.callback_query(F.data.startswith("admincat_"))
async def admin_category(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    category = callback.data.replace("admincat_", "")
    products = [p for p in products_db if p.get('category') == category]
    
    kb = []
    for p in products[:15]:
        kb.append([InlineKeyboardButton(text=f"❌ {p['name'][:30]}", callback_data=f"del_{p['id']}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_products")])
    
    await callback.message.edit_text(
        f"📦 {category}\n\n"
        f"Товаров: {len(products)}\n\n"
        f"Нажмите ❌ для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.callback_query(F.data.startswith("del_"))
async def delete_product(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    pid = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    load_products()
    
    await callback.answer("✅ Товар удален!", show_alert=True)
    await callback.message.edit_text(
        "✅ Товар успешно удален из каталога!",
        reply_markup=admin_menu()
    )

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new = cursor.fetchone()[0]
    await callback.message.edit_text(
        f"🔐 Админ-панель POIZON LAB\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🆕 Новых заказов: {new}",
        reply_markup=admin_menu()
    )

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders")
    total = cursor.fetchone()[0]
    
    stats_text = f"📊 Статистика POIZON LAB\n\n"
    stats_text += f"📦 Всего товаров: {len(products_db)}\n"
    stats_text += f"🛒 Всего заказов: {total}\n"
    stats_text += f"📱 Канал: {CHANNEL_ID}\n\n"
    stats_text += "Товары по категориям:\n"
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        if count > 0:
            stats_text += f"{cat}: {count}\n"
    
    await callback.message.edit_text(stats_text, reply_markup=admin_menu())

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
    orders = cursor.fetchall()
    
    if not orders:
        await callback.message.edit_text("📦 Заказов пока нет", reply_markup=admin_menu())
        return
    
    text = "📦 Последние 10 заказов:\n\n"
    for o in orders:
        text += f"🆔 #{o[0]} | @{o[2]}\n   {o[4][:30]}\n   💰 {o[5]} | {o[7]}\n\n"
    await callback.message.edit_text(text, reply_markup=admin_menu())

# ===== ЗАКАЗ ПО ССЫЛКЕ =====
@router.callback_query(F.data == "order_link")
async def order_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 Заказ по ссылке\n\n"
        "Отправьте ссылку на товар с сайта POIZON:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")]
        ])
    )
    await state.set_state(OrderLink.waiting_for_link)

@router.message(OrderLink.waiting_for_link)
async def link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("📏 Укажите размер товара:")
    await state.set_state(OrderLink.waiting_for_size)

@router.message(OrderLink.waiting_for_size)
async def size(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("💬 Добавьте комментарий к заказу:")
    await state.set_state(OrderLink.waiting_for_comment)

@router.message(OrderLink.waiting_for_comment)
async def comment(message: Message, state: FSMContext):
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
    
    await bot.send_message(ADMIN_ID,
        f"🔔 НОВЫЙ ЗАКАЗ ПО ССЫЛКЕ #{order_id}\n\n"
        f"👤 {order_data['full_name']}\n"
        f"📱 @{order_data['username']}\n"
        f"🆔 {order_data['user_id']}\n\n"
        f"🔗 {data['link']}\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 Комментарий: {message.text}")
    
    await message.answer(
        f"✅ Заказ #{order_id} принят!\n\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 {message.text}\n\n"
        f"⏳ Менеджер рассчитает стоимость и свяжется с вами!",
        reply_markup=main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    try:
        admin_chat = await bot.get_chat(ADMIN_ID)
        admin_username = admin_chat.username if admin_chat.username else "admin"
    except:
        admin_username = "admin"
    
    await callback.message.edit_text(
        f"💬 Техподдержка POIZON LAB\n\n"
        f"📞 Менеджер: @{admin_username}\n"
        f"⏰ Время работы: 24/7\n"
        f"⚡️ Среднее время ответа: 5 минут",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ])
    )

@router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_menu())

# ===== ЗАПУСК =====
async def main():
    dp.include_router(router)
    print("=" * 60)
    print("🤖 POIZON LAB БОТ ЗАПУЩЕН!")
    print(f"📱 Канал: {CHANNEL_ID}")
    print(f"📦 Товаров в базе: {len(products_db)}")
    print(f"🔄 Парсер: АВТОМАТИЧЕСКИЙ С ПРИОРИТЕТОМ КАТЕГОРИЙ")
    print("=" * 60)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
