import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import json

# Получение переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Состояния для заказа через ссылку
class OrderLink(StatesGroup):
    waiting_for_link = State()
    waiting_for_size = State()
    waiting_for_comment = State()

# Состояния для добавления товара (админ)
class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()

# База данных (в памяти, для простоты)
products_db = []
orders_db = []

# Проверка на админа
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Главное меню
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Заказ через каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🔗 Заказ через ссылку", callback_data="order_link")],
        [InlineKeyboardButton(text="💬 Техподдержка", callback_data="support")]
    ])
    return keyboard

# Админ меню
def admin_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="📋 Список товаров", callback_data="admin_list_products")],
        [InlineKeyboardButton(text="📦 Все заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    return keyboard

# Команда /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

# Команда /admin
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    await message.answer(
        "🔐 Админ-панель\n\nВыберите действие:",
        reply_markup=admin_menu()
    )

# Обработка кнопок главного меню
@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not products_db:
        await callback.message.edit_text(
            "📦 Каталог пуст. Пока нет товаров.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
        )
        return
    
    text = "📦 **Каталог товаров:**\n\n"
    keyboard = []
    
    for i, product in enumerate(products_db):
        text += f"{i+1}. {product['name']} - {product['price']} руб.\n"
        keyboard.append([InlineKeyboardButton(
            text=f"{product['name']}", 
            callback_data=f"product_{i}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

# Просмотр товара
@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = products_db[product_id]
    
    text = f"**{product['name']}**\n\n"
    text += f"📝 {product['description']}\n"
    text += f"💰 Цена: {product['price']} руб."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data=f"buy_{product_id}")],
        [InlineKeyboardButton(text="◀️ К каталогу", callback_data="catalog")]
    ])
    
    if product.get('photo'):
        await callback.message.delete()
        await bot.send_photo(
            callback.from_user.id,
            photo=product['photo'],
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# Оформление заказа из каталога
@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = products_db[product_id]
    
    order = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username or "Без username",
        'product': product['name'],
        'price': product['price'],
        'type': 'catalog'
    }
    orders_db.append(order)
    
    # Уведомление админа
    await bot.send_message(
        ADMIN_ID,
        f"🔔 **Новый заказ!**\n\n"
        f"От: @{order['username']} (ID: {order['user_id']})\n"
        f"Товар: {order['product']}\n"
        f"Цена: {order['price']} руб.",
        parse_mode="Markdown"
    )
    
    await callback.message.edit_text(
        f"✅ Ваш заказ принят!\n\n"
        f"Товар: {product['name']}\n"
        f"Цена: {product['price']} руб.\n\n"
        f"Скоро с вами свяжется администратор.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")]
        ])
    )

# Заказ через ссылку
@router.callback_query(F.data == "order_link")
async def start_order_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 Отправьте ссылку на товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
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
    
    order = {
        'user_id': message.from_user.id,
        'username': message.from_user.username or "Без username",
        'link': data['link'],
        'size': data['size'],
        'comment': message.text,
        'type': 'link'
    }
    orders_db.append(order)
    
    # Уведомление админа
    await bot.send_message(
        ADMIN_ID,
        f"🔔 **Новый заказ по ссылке!**\n\n"
        f"От: @{order['username']} (ID: {order['user_id']})\n"
        f"Ссылка: {order['link']}\n"
        f"Размер: {order['size']}\n"
        f"Комментарий: {order['comment']}",
        parse_mode="Markdown"
    )
    
    await message.answer(
        "✅ Ваш заказ принят! Скоро с вами свяжется администратор.",
        reply_markup=main_menu()
    )
    await state.clear()

# Техподдержка
@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💬 **Техподдержка**\n\n"
        f"Свяжитесь с администратором: @{(await bot.get_chat(ADMIN_ID)).username or 'admin'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
        ]),
        parse_mode="Markdown"
    )

# Админ: добавление товара
@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 Введите название товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await state.set_state(AddProduct.waiting_for_name)

@router.message(AddProduct.waiting_for_name)
async def process_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📄 Введите описание товара:")
    await state.set_state(AddProduct.waiting_for_description)

@router.message(AddProduct.waiting_for_description)
async def process_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("💰 Введите цену (только число):")
    await state.set_state(AddProduct.waiting_for_price)

@router.message(AddProduct.waiting_for_price)
async def process_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await message.answer(
            "📸 Отправьте фото товара или напишите 'пропустить':",
        )
        await state.set_state(AddProduct.waiting_for_photo)
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число:")

@router.message(AddProduct.waiting_for_photo, F.photo)
async def process_product_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    product = {
        'name': data['name'],
        'description': data['description'],
        'price': data['price'],
        'photo': photo_id
    }
    products_db.append(product)
    
    await message.answer(
        f"✅ Товар добавлен!\n\n"
        f"**{product['name']}**\n"
        f"{product['description']}\n"
        f"Цена: {product['price']} руб.",
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )
    await state.clear()

@router.message(AddProduct.waiting_for_photo, F.text)
async def process_product_no_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    
    product = {
        'name': data['name'],
        'description': data['description'],
        'price': data['price'],
        'photo': None
    }
    products_db.append(product)
    
    await message.answer(
        f"✅ Товар добавлен без фото!\n\n"
        f"**{product['name']}**\n"
        f"{product['description']}\n"
        f"Цена: {product['price']} руб.",
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )
    await state.clear()

# Админ: список товаров
@router.callback_query(F.data == "admin_list_products")
async def admin_list_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if not products_db:
        await callback.message.edit_text(
            "📦 Товаров пока нет.",
            reply_markup=admin_menu()
        )
        return
    
    text = "📦 **Список товаров:**\n\n"
    for i, product in enumerate(products_db):
        text += f"{i+1}. {product['name']} - {product['price']} руб.\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )

# Админ: все заказы
@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if not orders_db:
        await callback.message.edit_text(
            "📦 Заказов пока нет.",
            reply_markup=admin_menu()
        )
        return
    
    text = "📦 **Все заказы:**\n\n"
    for i, order in enumerate(orders_db):
        text += f"{i+1}. @{order['username']} - "
        if order['type'] == 'catalog':
            text += f"{order['product']} ({order['price']} руб.)\n"
        else:
            text += f"Заказ по ссылке (размер: {order['size']})\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )

# Возврат в главное меню
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔐 Админ-панель:",
        reply_markup=admin_menu()
    )

# Запуск бота
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
