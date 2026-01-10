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

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = "@asdasdadsads123312"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

CATEGORIES = {
    'Обувь': ['кроссовки', 'кросс', 'ботинки', 'тапки', 'сланцы', 'slides', 'туфли', 'boots', 'sneakers'],
    'Верхняя одежда': ['худи', 'hoodie', 'толстовка', 'свитшот', 'куртка', 'пуховик', 'пальто', 'парка', 'ветровка', 'бомбер', 'jacket', 'coat', 'кофта'],
    'Одежда': ['футболка', 'майка', 'шорты', 'джинсы', 'брюки', 'штаны', 'рубашка', 'shirt', 'pants', 'jeans'],
    'Сумки': ['сумка', 'рюкзак', 'клатч', 'кошелек', 'портмоне', 'bag', 'backpack', 'wallet'],
    'Аксессуары': ['часы', 'браслет', 'цепь', 'очки', 'кепка', 'шапка', 'ремень', 'носки', 'watch', 'belt', 'cap', 'hat'],
    'Косметика': ['крем', 'помада', 'тушь', 'духи', 'парфюм', 'маска', 'perfume', 'cream', 'serum', 'lipstick'],
    'Другое': []
}

conn = sqlite3.connect('poizon_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
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
    text_lower = text.lower()
    for cat, keywords in CATEGORIES.items():
        if cat == 'Другое':
            continue
        for keyword in keywords:
            if keyword in text_lower:
                return cat
    return 'Другое'

def load_products():
    global products_db
    cursor.execute('SELECT * FROM products ORDER BY created_at DESC')
    products_db = [{'id': r[0], 'name': r[1], 'description': r[2], 'price': r[3], 
                    'photo': r[4], 'source': r[5], 'post_id': r[6], 
                    'category': r[7] if len(r) > 7 else 'Другое'} for r in cursor.fetchall()]

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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="Заказ по ссылке", callback_data="order_link")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Управление товарами", callback_data="admin_products")],
        [InlineKeyboardButton(text="Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Назад", callback_data="back_main")]
    ])

def catalog_categories():
    kb = []
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        if count > 0:
            kb.append([InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"cat_{cat}")])
    kb.append([InlineKeyboardButton(text="Все товары", callback_data="cat_all")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def paginate_products(products, page=0, category='all'):
    per_page = 8
    start = page * per_page
    end = start + per_page
    filtered = [p for p in products if category == 'all' or p.get('category') == category]
    page_products = filtered[start:end]
    kb = []
    for p in page_products:
        kb.append([InlineKeyboardButton(text=f"{format_price(p['price'])} | {p['name'][:30]}", callback_data=f"product_{p['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"page_{category}_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{(len(filtered)-1)//per_page+1}", callback_data="pageinfo"))
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
    match1 = re.search(r'(d[ds]+?)s*[₽руб$RUB]', text, re.IGNORECASE)
    if match1:
        price = match1.group(1).replace(' ', '')
    else:
        match2 = re.search(r'цена[s-:]+(d[ds]+)', text, re.IGNORECASE)
        if match2:
            price = match2.group(1).replace(' ', '')
        else:
            match3 = re.search(r'\b(d{3,})\b', text)
            if match3:
                price = match3.group(1)
    lines = text.split('
')
    title = lines[0][:60].strip() if lines and len(lines[0]) > 5 else text[:60].strip() or f"Товар #{message.message_id}"
    category = detect_category(text)
    try:
        cursor.execute('INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id, category) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (title, text[:300], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id, category))
        conn.commit()
        if cursor.rowcount > 0:
            load_products()
            await bot.send_message(ADMIN_ID, f"Новый товар!

{category}
{title}
{format_price(price)} руб

Всего: {len(products_db)}")
    except Exception as e:
        print(f"Ошибка: {e}")

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(f"POIZON LAB

Товаров: {len(products_db)}
Канал: {CHANNEL_ID}", reply_markup=main_menu())

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
    new = cursor.fetchone()[0]
    await message.answer(f"Админ

Товаров: {len(products_db)}
Заказов: {new}", reply_markup=admin_menu())

@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text("Каталог пуст", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]]))
        return
    await callback.message.edit_text(f"Каталог ({len(products_db)} товаров)

Выберите категорию:", reply_markup=catalog_categories())

@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    kb, total = paginate_products(products_db, 0, category)
    await callback.message.edit_text(f"{category if category != 'all' else 'Все товары'}

Товаров: {total}", reply_markup=kb)

@router.callback_query(F.data.startswith("page_"))
async def paginate_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[-1])
    category = "_".join(parts[1:-1])
    kb, total = paginate_products(products_db, page, category)
    await callback.message.edit_text(f"{category if category != 'all' else 'Все товары'}

Товаров: {total}", reply_markup=kb)

@router.callback_query(F.data == "pageinfo")
async def pageinfo(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    if not p:
        await callback.answer("Товар не найден", show_alert=True)
        return
    text = f"{p['name']}

{p['description']}

{format_price(p['price'])} руб

{p.get('category', 'Другое')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заказать", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="Каталог", callback_data="catalog")]
    ])
    try:
        await callback.message.delete()
    except:
        pass
    if p.get('photo'):
        await bot.send_photo(callback.from_user.id, photo=p['photo'], caption=text, reply_markup=kb)
    else:
        await bot.send_message(callback.from_user.id, text=text, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    p = next((x for x in products_db if x['id'] == pid), None)
    if not p:
        await callback.answer("Товар удален", show_alert=True)
        return
    data = {'user_id': callback.from_user.id, 'username': callback.from_user.username or "no_username",
            'full_name': callback.from_user.full_name, 'product': p['name'], 'price': p['price'], 'type': 'catalog'}
    order_id = save_order(data)
    await bot.send_message(ADMIN_ID, f"ЗАКАЗ #{order_id}

{data['full_name']}
@{data['username']}

{p['name']}
{format_price(p['price'])} руб")
    await callback.answer("Заказ оформлен!", show_alert=True)
    try:
        await callback.message.delete()
    except:
        pass
    await bot.send_message(callback.from_user.id, f"ЗАКАЗ #{order_id} ОФОРМЛЕН!

{p['name']}
{format_price(p['price'])} руб

Менеджер скоро свяжется!", reply_markup=main_menu())

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
    category = callback.data.replace("admincat_", "")
    products = [p for p in products_db if p.get('category') == category]
    kb = []
    for p in products[:15]:
        kb.append([InlineKeyboardButton(text=f"Удалить {p['name'][:30]}", callback_data=f"del_{p['id']}")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="admin_products")])
    await callback.message.edit_text(f"{category} ({len(products)})

Нажмите для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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
    await callback.message.edit_text(f"Админ

Товаров: {len(products_db)}
Заказов: {new}", reply_markup=admin_menu())

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM orders")
    total = cursor.fetchone()[0]
    stats = f"Статистика

Товаров: {len(products_db)}
Заказов: {total}

"
    for cat in CATEGORIES.keys():
        count = len([p for p in products_db if p.get('category') == cat])
        if count > 0:
            stats += f"{cat}: {count}
"
    await callback.message.edit_text(stats, reply_markup=admin_menu())

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
    orders = cursor.fetchall()
    if not orders:
        await callback.message.edit_text("Заказов нет", reply_markup=admin_menu())
        return
    text = "Последние 10:

"
    for o in orders:
        text += f"#{o[0]} | @{o[2]}
{o[4][:30]}
{o[5]} | {o[7]}

"
    await callback.message.edit_text(text, reply_markup=admin_menu())

@router.callback_query(F.data == "order_link")
async def order_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте ссылку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="back_main")]]))
    await state.set_state(OrderLink.waiting_for_link)

@router.message(OrderLink.waiting_for_link)
async def link_handler(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Размер:")
    await state.set_state(OrderLink.waiting_for_size)

@router.message(OrderLink.waiting_for_size)
async def size_handler(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Комментарий:")
    await state.set_state(OrderLink.waiting_for_comment)

@router.message(OrderLink.waiting_for_comment)
async def comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    order_data = {'user_id': message.from_user.id, 'username': message.from_user.username or "no_username",
                  'full_name': message.from_user.full_name, 'product': f"По ссылке (размер {data['size']})",
                  'price': "Уточняется", 'type': 'link'}
    order_id = save_order(order_data)
    await bot.send_message(ADMIN_ID, f"ЗАКАЗ ПО ССЫЛКЕ #{order_id}

{order_data['full_name']}
@{order_data['username']}

{data['link']}
{data['size']}
{message.text}")
    await message.answer(f"Заказ #{order_id} принят!

Менеджер рассчитает стоимость!", reply_markup=main_menu())
    await state.clear()

@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    try:
        admin_chat = await bot.get_chat(ADMIN_ID)
        admin_username = admin_chat.username or "admin"
    except:
        admin_username = "admin"
    await callback.message.edit_text(f"Поддержка

@{admin_username}
24/7", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]]))

@router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())

async def main():
    dp.include_router(router)
    print("БОТ ЗАПУЩЕН!")
    print(f"Товаров: {len(products_db)}")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
