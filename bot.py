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

# Создание таблиц
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
CHANNEL_POSTS = set()
PARSER_DELAY = 600  # 10 минут

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
        [InlineKeyboardButton(text="🔄 Обновить канал", callback_data="parse_channel")],
        [InlineKeyboardButton(text=f"⏱ Delay: {PARSER_DELAY}s", callback_data="admin_delay")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

# ===== ПАРСЕР КАНАЛА =====
async def parse_channel():
    """Парсит новые посты из канала"""
    global CHANNEL_POSTS
    
    try:
        # Получаем последние 20 сообщений
        messages = await bot.get_chat_history(CHANNEL_ID, limit=20)
        new_count = 0
        
        for message in reversed(messages):
            # Пропускаем если уже обработан
            if message.message_id in CHANNEL_POSTS:
                continue
            
            # Нужно фото
            if not message.photo:
                continue
            
            text = message.caption or message.text or ""
            
            # Извлекаем цену
            price_match = re.search(r'(\d[\d\s]*?)(?=\s*[₽руб$RUB])', text)
            if price_match:
                price = price_match.group(1).replace(' ', '')
            else:
                price = "Цена в ЛС"
            
            # Название товара (первая строка)
            lines = text.split('\n')
            title = lines[0][:60] if lines else f"Товар #{message.message_id}"
            
            # Сохраняем в БД
            try:
                cursor.execute('''
                INSERT OR IGNORE INTO products (name, description, price, photo, source, post_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (title, text[:300], price, message.photo[-1].file_id, CHANNEL_ID, message.message_id))
                
                if cursor.rowcount > 0:
                    new_count += 1
                
                conn.commit()
            except Exception as e:
                print(f"Ошибка сохранения товара: {e}")
            
            CHANNEL_POSTS.add(message.message_id)
        
        # Перезагружаем товары
        load_products()
        
        # Уведомление админу
        if new_count > 0:
            await bot.send_message(
                ADMIN_ID,
                f"✅ Парсер обновлен!\n\n"
                f"Добавлено новых товаров: {new_count}\n"
                f"Всего в каталоге: {len(products_db)}"
            )
        
        print(f"✅ Парсер: добавлено {new_count} товаров")
        
    except Exception as e:
        error_msg = f"❌ Ошибка парсера: {e}"
        print(error_msg)
        try:
            await bot.send_message(ADMIN_ID, error_msg)
        except:
            pass

async def auto_parser():
    """Авто-парсинг с интервалом"""
    global PARSER_DELAY
    await asyncio.sleep(5)  # Ждем 5 сек после запуска
    
    while True:
        await parse_channel()
        await asyncio.sleep(PARSER_DELAY)

# ===== КОМАНДЫ =====
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Добро пожаловать в POIZON LAB!\n\n"
        f"📦 Товаров в каталоге: {len(products_db)}\n"
        f"🔄 Автоматический парсинг: {CHANNEL_ID}\n\n"
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
        f"🔐 Админ-панель\n\n"
        f"📦 Товаров: {len(products_db)}\n"
        f"🛒 Заказов всего: {total_orders}\n"
        f"🆕 Новых заказов: {new_orders}\n"
        f"⏱ Интервал парсера: {PARSER_DELAY}с ({PARSER_DELAY//60}м)\n"
        f"📱 Канал: {CHANNEL_ID}",
        reply_markup=admin_menu()
    )

@router.message(Command("delay"))
async def cmd_delay(message: Message):
    global PARSER_DELAY
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Только для админа!")
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            raise ValueError()
        
        new_delay = int(args[1])
        
        if new_delay < 30:
            await message.answer("❌ Минимальный интервал: 30 секунд")
            return
        
        PARSER_DELAY = new_delay
        await message.answer(
            f"✅ Интервал парсера изменен!\n\n"
            f"⏱ Новый интервал: {new_delay} сек ({new_delay//60} мин)"
        )
        print(f"⏱ Интервал изменен: {new_delay}с")
        
    except (ValueError, IndexError):
        await message.answer(
            f"📊 Текущий интервал парсера: {PARSER_DELAY} сек\n\n"
            f"Использование:\n"
            f"/delay 60 — каждую минуту\n"
            f"/delay 300 — каждые 5 минут\n"
            f"/delay 1800 — каждые 30 минут"
        )

# ===== КАТАЛОГ =====
@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            "📦 Каталог пока пуст\n\n"
            "🔄 Ожидаем посты из канала...\n"
            f"Парсим: {CHANNEL_ID}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="parse_channel")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
            ])
        )
        return
    
    text = f"📦 Каталог POIZON LAB\n\n"
    text += f"Всего товаров: {len(products_db)}\n\n"
    
    keyboard = []
    for product in products_db[:10]:
        button_text = f"{format_price(product['price'])} ₽ | {product['name'][:25]}"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"product_{product['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="parse_channel")])
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
        f"🛍 Товар: {product['name']}\n"
        f"💰 Цена: {format_price(product['price'])} ₽\n\n"
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
        "Отправьте ссылку на товар с сайта POIZON:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")]
        ])
    )
    await state.set_state(OrderLink.waiting_for_link)

@router.message(OrderLink.waiting_for_link)
async def process_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("📏 Укажите размер товара:")
    await state.set_state(OrderLink.waiting_for_size)

@router.message(OrderLink.waiting_for_size)
async def process_size(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("💬 Добавьте комментарий к заказу:")
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
        f"👤 Клиент: {order_data['full_name']}\n"
        f"📱 Username: @{order_data['username']}\n"
        f"🆔 User ID: {order_data['user_id']}\n\n"
        f"🔗 Ссылка: {data['link']}\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 Комментарий: {message.text}"
    )
    
    # Подтверждение пользователю
    await message.answer(
        f"✅ Заказ #{order_id} принят!\n\n"
        f"📏 Размер: {data['size']}\n"
        f"💬 Комментарий: {message.text}\n\n"
        f"⏳ Менеджер рассчитает стоимость и свяжется с вами!",
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
        f"💬 Техническая поддержка\n\n"
        f"📞 Свяжитесь с менеджером:\n"
        f"👤 @{admin_username}\n\n"
        f"⏰ Время работы: Круглосуточно\n"
        f"⚡️ Среднее время ответа: 5 минут",
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
        f"📊 Статистика магазина\n\n"
        f"📦 Товаров в каталоге: {len(products_db)}\n"
        f"🛒 Заказов всего: {total_orders}\n"
        f"🆕 Новых заказов: {new_orders}\n"
        f"⏱ Интервал парсера: {PARSER_DELAY}с ({PARSER_DELAY//60}м)\n"
        f"📱 Канал: {CHANNEL_ID}\n\n"
        f"🗄️ База данных: poizon_bot.db",
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

@router.callback_query(F.data == "parse_channel")
async def manual_parse(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    await callback.answer("🔄 Обновление канала...")
    await parse_channel()
    await callback.answer("✅ Канал обновлен!", show_alert=True)

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
    
    # Запуск авто-парсера
    asyncio.create_task(auto_parser())
    
    print("=" * 50)
    print("🤖 POIZON LAB бот запущен!")
    print(f"📱 Парсит канал: {CHANNEL_ID}")
    print(f"⏱ Интервал парсера: {PARSER_DELAY} секунд ({PARSER_DELAY//60} минут)")
    print(f"📦 Товаров в базе: {len(products_db)}")
    print(f"🗄️ База данных: poizon_bot.db")
    print("=" * 50)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
