import os
import asyncio
import re
import sqlite3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = "@asdasdadsads123312"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

CATEGORIES = {
    'Обувь': ['кроссовки', 'кросс', 'ботинки', 'тапки'],
    'Верхняя одежда': ['худи', 'толстовка', 'куртка', 'пуховик'],
    'Одежда': ['футболка', 'майка', 'шорты', 'джинсы'],
    'Сумки': ['сумка', 'рюкзак', 'кошелек'],
    'Аксессуары': ['часы', 'браслет', 'кепка'],
    'Косметика': ['крем', 'помада', 'духи'],
    'Другое': []
}

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
    category TEXT DEFAULT 'Другое',
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

def detect_category(text):
    text = text.lower()
    for cat, words in CATEGORIES.items():
        if cat == 'Другое':
            continue
        for word in words:
            if word in text:
                return cat
    return 'Другое'

def load_products():
    global products_db
    cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
    products_db = []
    for r in cursor.fetchall():
        products_db.append({
            'id': r[0], 'name': r[1], 'description': r[2], 'price': r[3],
            'photo': r[4], 'source': r[5], 'post_id': r[6],
            'category': r[7] if len(r) > 7 else 'Другое'
        })

def save_order(data):
    cursor.execute('INSERT INTO orders (user_id, username, full_name, product, price, type) VALUES (?, ?, ?, ?, ?, ?)',
        (data['user_id'], data['username'], data['full_name'], data['product'], data['price'], data['type']))
    conn.commit()
    return cursor.lastrowid

def format_price(price):
    return re.sub(r'(d)(?=(d{3})+(?!d))', r'\u0001 ', str(price).replace(' ', ''))

load_products()

class OrderLink(StatesGroup):
    waiting_for_link = State()
    waiting_for_size = State()
    waiting_for_comment = State()

def main_menu():
    kb = [
        [InlineKeyboardButton(text="Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="Заказ по ссылке", callback_data="order_link")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton(text="Товары", callback_data="admin_products")],
        [InlineKeyboardButton(text="Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def catalog_menu():
    kb = []
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        if count > 0:
            kb.append([InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"cat_{cat}")])
    kb.append([InlineKeyboardButton(text="Все товары", callback_data="cat_all")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def paginate_products(products, page, category):
    per_page = 8
    filtered = [p for p in products if category == 'all' or p.get('category') == category]
    start = page * per_page
    end = start + per_page
    kb = []
    for p in filtered[start:end]:
        price_text = format_price(p['price']) + ' руб'
        name_text = p['name'][:30]
        btn_text = f"{price_text} | {name_text}"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"product_{p['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"page_{category}_{page-1}"))
    page_text = f"{page+1}/{(len(filtered)-1)//per_page+1}"
    nav.append(InlineKeyboardButton(text=page_text, callback_data="pageinfo"))
    if end < len(filtered):
        nav.append(InlineKeyboardButton(text="Далее", callback_data=f"page_{category}_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="Категории", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=kb), len(filtered)

@router.channel_post()
async def auto_parse(message: Message):
    try:
        if not message.chat.username or f"@{message.chat.username}" != CHANNEL_ID:
            return
    except:
        return
    if not message.photo:
        return
    text = message.caption or ""
    price = "Цена в ЛС"
    m1 = re.search(r'(d[ds]+?)s*[₽руб]', text, re.IGNORECASE)
    if m1:
        price = m1.group(1).replace(' ', '')
    else:
        m2 = re.search(r'\b(d{3,})\b', text)
        if m2:
            price = m2.group(1)
    lines = text.split('
')
    title = lines[0][:60].strip() if lines else f"Товар #{message.message_id}"
    category = detect_category(text)
    try:
        cursor.execute('INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id, category) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (title, text[:300], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id, category))
        conn.commit()
        if cursor.rowcount > 0:
            load_products()
            msg = f"Новый товар

{category}
{title}
{format_price(price)} руб

Всего: {len(products_db)}"
            await bot.send_message(ADMIN_ID, msg)
    except Exception as e:
        print(f"Ошибка: {e}")

@router.message(CommandStart())
async def cmd_start(message: Message):
    msg = f"Добро пожаловать в POIZON LAB!

Товаров: {len(products_db)}
Канал: {CHANNEL_ID}

Выберите действие:"
    await message.answer(msg, reply_markup=main_menu())

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещен")
        return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new = cursor.fetchone()[0]
    msg = f"Админ панель

Товаров: {len(products_db)}
Заказов: {new}"
    await message.answer(msg, reply_markup=admin_menu())

@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]])
        await callback.message.edit_text("Каталог пуст", reply_markup=kb)
        return
    msg = f"Каталог POIZON LAB

Всего: {len(products_db)}

Выберите категорию:"
    await callback.message.edit_text(msg, reply_markup=catalog_menu())

@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback: CallbackQuery):
    category = callback.data[4:]
    kb, total = paginate_products(products_db, 0, category)
    cat_name = category if category != 'all' else 'Все товары'
    msg = f"{cat_name}

Товаров: {total}"
    await callback.message.edit_text(msg, reply_markup=kb)

@router.callback_query(F.data.startswith("page_"))
async def page_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[-1])
    category = "_".join(parts[1:-1])
    kb, total = paginate_products(products_db, page, category)
    cat_name = category if category != 'all' else 'Все товары'
    msg = f"{cat_name}

Товаров: {total}"
    await callback.message.edit_text(msg, reply_markup=kb)

@router.callback_query(F.data == "pageinfo")
async def pageinfo(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    if not p:
        await callback.answer("Товар не найден")
        return
    msg = f"{p['name']}

{p['description']}

{format_price(p['price'])} руб

{p.get('category')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заказать", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="Каталог", callback_data="catalog")]
    ])
    try:
        await callback.message.delete()
    except:
        pass
    if p.get('photo'):
        await bot.send_photo(callback.from_user.id, p['photo'], caption=msg, reply_markup=kb)
    else:
        await bot.send_message(callback.from_user.id, msg, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    if not p:
        await callback.answer("Товар удален")
        return
    data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "no_username",
        'full_name': callback.from_user.full_name,
        'product': p['name'],
        'price': p['price'],
        'type': 'catalog'
    }
    oid = save_order(data)
    admin_msg = f"ЗАКАЗ #{oid}

{data['full_name']}
@{data['username']}

{p['name']}
{format_price(p['price'])} руб"
    await bot.send_message(ADMIN_ID, admin_msg)
    await callback.answer("Заказ оформлен!", show_alert=True)
    try:
        await callback.message.delete()
    except:
        pass
    user_msg = f"ЗАКАЗ #{oid} ОФОРМЛЕН!

{p['name']}
{format_price(p['price'])} руб

Менеджер скоро свяжется!"
    await bot.send_message(callback.from_user.id, user_msg, reply_markup=main_menu())

@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    kb = []
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        kb.append([InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"admincat_{cat}")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="admin_back")])
    await callback.message.edit_text("Управление товарами", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("admincat_"))
async def admin_category(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cat = callback.data[9:]
    prods = [p for p in products_db if p.get('category') == cat]
    kb = []
    for p in prods[:15]:
        kb.append([InlineKeyboardButton(text=f"Удалить {p['name'][:25]}", callback_data=f"del_{p['id']}")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="admin_products")])
    msg = f"{cat} ({len(prods)})

Нажмите для удаления:"
    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("del_"))
async def delete_product(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    pid = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    load_products()
    await callback.answer("Удалено!", show_alert=True)
    await callback.message.edit_text("Товар удален", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new = cursor.fetchone()[0]
    msg = f"Админ панель

Товаров: {len(products_db)}
Заказов: {new}"
    await callback.message.edit_text(msg, reply_markup=admin_menu())

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
    orders = cursor.fetchall()
    if not orders:
        await callback.message.edit_text("Заказов пока нет", reply_markup=admin_menu())
        return
    msg = "Последние 10 заказов:

"
    for o in orders:
        msg += f"#{o[0]} | @{o[2]}
{o[4][:30]}
{o[5]}

"
    await callback.message.edit_text(msg, reply_markup=admin_menu())

@router.callback_query(F.data == "order_link")
async def order_link(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="back_main")]])
    await callback.message.edit_text("Заказ по ссылке

Отправьте ссылку:", reply_markup=kb)
    await state.set_state(OrderLink.waiting_for_link)

@router.message(OrderLink.waiting_for_link)
async def link_handler(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Укажите размер:")
    await state.set_state(OrderLink.waiting_for_size)

@router.message(OrderLink.waiting_for_size)
async def size_handler(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Добавьте комментарий:")
    await state.set_state(OrderLink.waiting_for_comment)

@router.message(OrderLink.waiting_for_comment)
async def comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    order_data = {
        'user_id': message.from_user.id,
        'username': message.from_user.username or "no_username",
        'full_name': message.from_user.full_name,
        'product': f"По ссылке (размер {data['size']})",
        'price': "Уточняется",
        'type': 'link'
    }
    oid = save_order(order_data)
    admin_msg = f"ЗАКАЗ ПО ССЫЛКЕ #{oid}

{order_data['full_name']}
@{order_data['username']}

{data['link']}
Размер: {data['size']}
{message.text}"
    await bot.send_message(ADMIN_ID, admin_msg)
    user_msg = f"Заказ #{oid} принят!

Менеджер рассчитает стоимость!"
    await message.answer(user_msg, reply_markup=main_menu())
    await state.clear()

@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    try:
        admin = await bot.get_chat(ADMIN_ID)
        username = admin.username or "admin"
    except:
        username = "admin"
    msg = f"Техподдержка

Менеджер: @{username}
Работаем: 24/7"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]])
    await callback.message.edit_text(msg, reply_markup=kb)

@router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())

async def main():
    print("=" * 60)
    print("БОТ ЗАПУСКАЕТСЯ...")
    print(f"Товаров: {len(products_db)}")
    print(f"Канал: {CHANNEL_ID}")
    print("=" * 60)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
