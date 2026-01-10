import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# --- CONFIGURATION ---
TOKEN = os.environ.get("TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
CHANNEL_ID = os.environ.get("CHANNEL_ID") # ID канала для автопостинга (например, -100...)

CATALOG_FILE = "catalog.json"
ORDERS_FILE = "orders.json"

# --- STATES ---
(
    MENU, 
    LINK_1, LINK_2, LINK_3, 
    CAT_1, CAT_2, CAT_3, 
    SUPPORT,
    ADMIN_ADD_PHOTO, ADMIN_ADD_NAME, ADMIN_ADD_PRICE, ADMIN_ADD_SIZES,
    ADMIN_BROADCAST
) = range(13)

# --- DATABASE OPERATIONS ---
def init_files():
    for file in [CATALOG_FILE, ORDERS_FILE]:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as f:
                json.dump([], f)

def load_data(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- KEYBOARDS ---
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Заказать по ссылке", callback_data="order_link")],
        [InlineKeyboardButton("📦 Просмотреть каталог", callback_data="catalog_list")],
        [InlineKeyboardButton("💬 Техподдержка", callback_data="support")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Все заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Удалить товар", callback_data="admin_del")],
        [InlineKeyboardButton("📢 Пост в канал", callback_data="admin_post")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="to_start")]
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="to_start")]])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👋 **Добро пожаловать в наш магазин!**\n\nВыберите интересующий раздел ниже:"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    return MENU

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return MENU
    await update.message.reply_text("🛠 **Панель администратора**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    return MENU

# --- ORDER BY LINK ---
async def order_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔗 **Шаг 1/3**: Пришлите ссылку на товар:", reply_markup=back_kb(), parse_mode="Markdown")
    return LINK_1

async def order_link_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link_url'] = update.message.text
    await update.message.reply_text("📏 **Шаг 2/3**: Укажите нужный размер:", reply_markup=back_kb(), parse_mode="Markdown")
    return LINK_2

async def order_link_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link_size'] = update.message.text
    await update.message.reply_text("🎨 **Шаг 3/3**: Укажите цвет или комментарий к заказу:", reply_markup=back_kb(), parse_mode="Markdown")
    return LINK_3

async def order_link_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order = {
        "type": "link", "user_id": user.id, "product": "По ссылке",
        "messages": [context.user_data['link_url'], context.user_data['link_size'], update.message.text]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    
    await context.bot.send_message(OWNER_ID, f"🆕 **НОВЫЙ ЗАКАЗ (ССЫЛКА)**\n👤 От: `{user.id}`\n1️⃣ Ссылка: {order['messages'][0]}\n2️⃣ Размер: {order['messages'][1]}\n3️⃣ Коммент: {order['messages'][2]}", parse_mode="Markdown")
    await update.message.reply_text("✅ **Заказ успешно оформлен!**\nНаш менеджер свяжется с вами.")
    return await start(update, context)

# --- CATALOG ---
async def catalog_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await update.callback_query.edit_message_text("📭 Каталог пока пуст.", reply_markup=get_main_keyboard())
        return MENU
    
    await update.callback_query.delete_message()
    for item in items:
        caption = f"🛍 **{item['name']}**\n\n💰 Цена: `{item['price']}`\n📏 Размеры: `{item['sizes']}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Купить", callback_data=f"buy_{item['id']}")]])
        await context.bot.send_photo(update.effective_chat.id, item['photo_id'], caption=caption, reply_markup=kb, parse_mode="Markdown")
    
    await context.bot.send_message(update.effective_chat.id, "Выше представлены все товары.", reply_markup=get_main_keyboard())
    return MENU

async def buy_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['buy_id'] = update.callback_query.data.split('_')[1]
    await context.bot.send_message(update.effective_chat.id, "📏 **Шаг 1/3**: Укажите размер:", parse_mode="Markdown")
    return CAT_1

async def buy_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_size'] = update.message.text
    await update.message.reply_text("🎨 **Шаг 2/3**: Цвет / Комментарий:", parse_mode="Markdown")
    return CAT_2

async def buy_step_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_comment'] = update.message.text
    await update.message.reply_text("📍 **Шаг 3/3**: Контактные данные и адрес доставки:", parse_mode="Markdown")
    return CAT_3

async def buy_step_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = load_data(CATALOG_FILE)
    item = next((i for i in items if str(i['id']) == context.user_data['buy_id']), {"name": "Неизвестно"})
    order = {
        "type": "catalog", "user_id": update.effective_user.id, "product": item['name'],
        "messages": [context.user_data['buy_size'], context.user_data['buy_comment'], update.message.text]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    
    await context.bot.send_message(OWNER_ID, f"🛍 **ЗАКАЗ ИЗ КАТАЛОГА**\n📦 Товар: {item['name']}\n👤 От: `{update.effective_user.id}`\n1️⃣ Размер: {order['messages'][0]}\n2️⃣ Коммент: {order['messages'][1]}\n3️⃣ Адрес: {order['messages'][2]}", parse_mode="Markdown")
    await update.message.reply_text("✅ **Заказ принят!** Ожидайте сообщения от администратора.")
    return await start(update, context)

# --- ADMIN FUNCTIONS ---
async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📸 Отправьте **фото** товара:", reply_markup=back_kb(), parse_mode="Markdown")
    return ADMIN_ADD_PHOTO

async def admin_add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['a_photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("🏷 Введите **название** товара:", reply_markup=back_kb(), parse_mode="Markdown")
    return ADMIN_ADD_NAME

async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['a_name'] = update.message.text
    await update.message.reply_text("💵 Введите **цену**:", reply_markup=back_kb(), parse_mode="Markdown")
    return ADMIN_ADD_PRICE

async def admin_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['a_price'] = update.message.text
    await update.message.reply_text("📏 Введите **размеры** (через запятую):", reply_markup=back_kb(), parse_mode="Markdown")
    return ADMIN_ADD_SIZES

async def admin_add_sizes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = load_data(CATALOG_FILE)
    new_item = {
        "id": str(update.message.message_id),
        "name": context.user_data['a_name'],
        "photo_id": context.user_data['a_photo'],
        "price": context.user_data['a_price'],
        "sizes": update.message.text
    }
    items.append(new_item)
    save_data(CATALOG_FILE, items)
    await update.message.reply_text("✅ **Товар добавлен в каталог!**")
    return await start(update, context)

async def admin_del_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await update.callback_query.edit_message_text("Каталог пуст.")
        return MENU
    kb = [[InlineKeyboardButton(f"🗑 {i['name']}", callback_data=f"del_{i['id']}")] for i in items]
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="to_start")])
    await update.callback_query.edit_message_text("Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(kb))
    return MENU

async def admin_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = update.callback_query.data.split('_')[1]
    items = [i for i in load_data(CATALOG_FILE) if i['id'] != item_id]
    save_data(CATALOG_FILE, items)
    await update.callback_query.edit_message_text("🗑 Товар удален.")
    return await start(update, context)

async def admin_orders_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    orders = load_data(ORDERS_FILE)
    if not orders:
        await context.bot.send_message(update.effective_chat.id, "Заказов пока нет.")
        return MENU
    for o in orders:
        txt = f"📝 **Заказ:** {o['product']}\n👤 **User ID:** `{o['user_id']}`\n🔹 {o['messages'][0]}\n🔹 {o['messages'][1]}\n🔹 {o['messages'][2]}"
        await context.bot.send_message(update.effective_chat.id, txt, parse_mode="Markdown")
    return MENU

async def admin_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not CHANNEL_ID:
        await update.callback_query.edit_message_text("❌ CHANNEL_ID не настроен в переменных окружения.")
        return MENU
    await update.callback_query.edit_message_text("📢 Отправьте сообщение (текст или фото с описанием), которое нужно переслать в канал:", reply_markup=back_kb())
    return ADMIN_BROADCAST

async def admin_post_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.copy(chat_id=CHANNEL_ID)
        await update.message.reply_text("✅ Сообщение опубликовано в канале!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    return await start(update, context)

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📌 Опишите вашу проблему/вопрос. Мы ответим в ближайшее время:", reply_markup=back_kb())
    return SUPPORT

async def support_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(OWNER_ID, f"🆘 **ТЕХПОДДЕРЖКА**\n👤 От: `{update.effective_user.id}`\n💬 Текст: {update.message.text}", parse_mode="Markdown")
    await update.message.reply_text("✅ Ваше сообщение отправлено администратору.")
    return await start(update, context)

# --- MAIN ---
if __name__ == "__main__":
    init_files()
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(start, pattern="^to_start$"),
        ],
        states={
            MENU: [
                CallbackQueryHandler(order_link_start, pattern="^order_link$"),
                CallbackQueryHandler(catalog_list, pattern="^catalog_list$"),
                CallbackQueryHandler(support_start, pattern="^support$"),
                CallbackQueryHandler(admin_add_start, pattern="^admin_add$"),
                CallbackQueryHandler(admin_del_list, pattern="^admin_del$"),
                CallbackQueryHandler(admin_orders_view, pattern="^admin_orders$"),
                CallbackQueryHandler(admin_post_start, pattern="^admin_post$"),
                CallbackQueryHandler(admin_del_confirm, pattern="^del_"),
                CallbackQueryHandler(buy_item_start, pattern="^buy_"),
                CallbackQueryHandler(start, pattern="^to_start$"),
            ],
            LINK_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_1), CallbackQueryHandler(start, pattern="^to_start$")],
            LINK_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_2), CallbackQueryHandler(start, pattern="^to_start$")],
            LINK_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_3), CallbackQueryHandler(start, pattern="^to_start$")],
            CAT_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_1)],
            CAT_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_2)],
            CAT_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_3)],
            SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_handle), CallbackQueryHandler(start, pattern="^to_start$")],
            ADMIN_ADD_PHOTO: [MessageHandler(filters.PHOTO, admin_add_photo), CallbackQueryHandler(start, pattern="^to_start$")],
            ADMIN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name), CallbackQueryHandler(start, pattern="^to_start$")],
            ADMIN_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_price), CallbackQueryHandler(start, pattern="^to_start$")],
            ADMIN_ADD_SIZES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_sizes), CallbackQueryHandler(start, pattern="^to_start$")],
            ADMIN_BROADCAST: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, admin_post_execute), CallbackQueryHandler(start, pattern="^to_start$")],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(start, pattern="^to_start$")],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.run_polling()
