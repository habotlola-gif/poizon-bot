import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

TOKEN = os.environ.get("TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

CATALOG_FILE = "catalog.json"
ORDERS_FILE = "orders.json"

# Состояния
MENU, LINK_1, LINK_2, LINK_3 = range(4)
CAT_1, CAT_2, CAT_3 = range(4, 7)
ADMIN_PHOTO, ADMIN_NAME, ADMIN_PRICE, ADMIN_SIZES = range(7, 11)
SUPPORT = range(11, 12)

def init_files():
    if not os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def load_data(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛒 Заказать через ссылку", callback_data="order_link")],
        [InlineKeyboardButton("📦 Каталог товаров", callback_data="catalog_list")],
        [InlineKeyboardButton("💬 Техподдержка", callback_data="support")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📦 Все заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("❌ Удалить товар", callback_data="admin_del")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Добро пожаловать! Выберите действие:"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_keyboard())
    return MENU

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return MENU
    await update.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())
    return MENU

async def order_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Шаг 1/3: Отправьте ссылку на товар:")
    return LINK_1

async def order_link_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link_url'] = update.message.text
    await update.message.reply_text("Шаг 2/3: Отправьте размер:")
    return LINK_2

async def order_link_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link_size'] = update.message.text
    await update.message.reply_text("Шаг 3/3: Отправьте цвет / комментарий:")
    return LINK_3

async def order_link_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    user_id = update.effective_user.id
    order = {
        "type": "link",
        "user_id": user_id,
        "product": None,
        "messages": [context.user_data['link_url'], context.user_data['link_size'], comment]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    await context.bot.send_message(OWNER_ID, f"📦 ЗАКАЗ ПО ССЫЛКЕ\nID: {user_id}\n1: {order['messages'][0]}\n2: {order['messages'][1]}\n3: {order['messages'][2]}")
    await update.message.reply_text("✅ Заказ принят!")
    return await start(update, context)

async def catalog_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await update.callback_query.edit_message_text("Каталог пуст.", reply_markup=get_main_keyboard())
        return MENU
    for item in items:
        cap = f"📦 {item['name']}\n💰 Цена: {item['price']}\n📏 Размеры: {item['sizes']}"
        kb = [[InlineKeyboardButton("Заказать", callback_data=f"buy_{item['id']}")]]
        await context.bot.send_photo(update.effective_chat.id, item['photo_id'], caption=cap, reply_markup=InlineKeyboardMarkup(kb))
    return MENU

async def buy_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['buy_id'] = update.callback_query.data.split('_')[1]
    await context.bot.send_message(update.effective_chat.id, "Шаг 1/3: Укажите размер:")
    return CAT_1

async def buy_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_size'] = update.message.text
    await update.message.reply_text("Шаг 2/3: Укажите цвет / комментарий:")
    return CAT_2

async def buy_step_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_comment'] = update.message.text
    await update.message.reply_text("Шаг 3/3: Укажите адрес / контакт:")
    return CAT_3

async def buy_step_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = load_data(CATALOG_FILE)
    item = next((i for i in items if str(i['id']) == str(context.user_data['buy_id'])), None)
    name = item['name'] if item else "Удаленный товар"
    order = {
        "type": "catalog",
        "user_id": user_id,
        "product": name,
        "messages": [context.user_data['buy_size'], context.user_data['buy_comment'], update.message.text]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    await context.bot.send_message(OWNER_ID, f"🛍️ ЗАКАЗ ИЗ КАТАЛОГА\nТовар: {name}\nID: {user_id}\n1: {order['messages'][0]}\n2: {order['messages'][1]}\n3: {order['messages'][2]}")
    await update.message.reply_text("✅ Товар заказан!")
    return await start(update, context)

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Опишите ваш вопрос:")
    return SUPPORT

async def support_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(OWNER_ID, f"💬 ТЕХПОДДЕРЖКА\nID: {update.effective_user.id}\nТекст: {update.message.text}")
    await update.message.reply_text("Отправлено.")
    return await start(update, context)

async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Отправьте ФОТО товара:")
    return ADMIN_PHOTO

async def admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p'] = update.message.photo[-1].file_id
    await update.message.reply_text("Введите НАЗВАНИЕ:")
    return ADMIN_NAME

async def admin_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_n'] = update.message.text
    await update.message.reply_text("Введите ЦЕНУ:")
    return ADMIN_PRICE

async def admin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_pr'] = update.message.text
    await update.message.reply_text("Введите РАЗМЕРЫ через запятую:")
    return ADMIN_SIZES

async def admin_sizes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = load_data(CATALOG_FILE)
    item = {
        "id": int(update.message.message_id),
        "name": context.user_data['new_n'],
        "photo_id": context.user_data['new_p'],
        "price": context.user_data['new_pr'],
        "sizes": update.message.text
    }
    items.append(item)
    save_data(CATALOG_FILE, items)
    await update.message.reply_text("✅ Товар добавлен!")
    return await start(update, context)

async def admin_del_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await update.callback_query.edit_message_text("Каталог пуст.")
        return MENU
    kb = [[InlineKeyboardButton(f"❌ {i['name']}", callback_data=f"del_{i['id']}")] for i in items]
    await update.callback_query.edit_message_text("Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(kb))
    return MENU

async def admin_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split('_')[1])
    items = load_data(CATALOG_FILE)
    items = [i for i in items if i['id'] != item_id]
    save_data(CATALOG_FILE, items)
    await update.callback_query.edit_message_text("🗑️ Удалено.")
    return await start(update, context)

async def admin_orders_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    orders = load_data(ORDERS_FILE)
    if not orders:
        await context.bot.send_message(update.effective_chat.id, "Заказов нет.")
        return MENU
    for o in orders:
        txt = f"Тип: {o['type']}\nID: {o['user_id']}\nТовар: {o['product']}\nИнфо: {o['messages']}"
        await context.bot.send_message(update.effective_chat.id, txt)
    return MENU

if __name__ == "__main__":
    init_files()
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("admin", admin_panel),
        ],
        states={
            MENU: [
                CallbackQueryHandler(order_link_start, pattern="^order_link$"),
                CallbackQueryHandler(catalog_list, pattern="^catalog_list$"),
                CallbackQueryHandler(support_start, pattern="^support$"),
                CallbackQueryHandler(admin_add_start, pattern="^admin_add$"),
                CallbackQueryHandler(admin_del_list, pattern="^admin_del$"),
                CallbackQueryHandler(admin_orders_view, pattern="^admin_orders$"),
                CallbackQueryHandler(admin_del_confirm, pattern="^del_"),
                CallbackQueryHandler(buy_item_start, pattern="^buy_"),
            ],
            LINK_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_1)],
            LINK_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_2)],
            LINK_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_link_3)],
            CAT_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_1)],
            CAT_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_2)],
            CAT_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_step_3)],
            SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_handle)],
            ADMIN_PHOTO: [MessageHandler(filters.PHOTO, admin_photo)],
            ADMIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_name)],
            ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_price)],
            ADMIN_SIZES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_sizes)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.run_polling()
