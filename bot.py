import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

MENU, LINK_1, LINK_2, LINK_3 = range(4)
CAT_1, CAT_2, CAT_3 = range(4, 7)
ADMIN_PHOTO, ADMIN_NAME, ADMIN_PRICE, ADMIN_SIZES = range(7, 11)
SUPPORT = range(11, 12)

def init_files():
    for file in [CATALOG_FILE, ORDERS_FILE]:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as f:
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
        return
    await update.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())

async def order_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Шаг 1/3: Отправьте ссылку на товар:")
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
    user = update.effective_user
    order = {
        "type": "link",
        "user_id": user.id,
        "product": None,
        "messages": [context.user_data['link_url'], context.user_data['link_size'], comment]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    
    admin_msg = f"📦 НОВЫЙ ЗАКАЗ (ССЫЛКА)\nОт: {user.id}\n1: {order['messages'][0]}\n2: {order['messages'][1]}\n3: {order['messages'][2]}"
    await context.bot.send_message(chat_id=OWNER_ID, text=admin_msg)
    
    await update.message.reply_text("✅ Заказ оформлен!")
    return await start(update, context)

async def catalog_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await query.edit_message_text("Каталог пуст.", reply_markup=get_main_keyboard())
        return MENU
    
    for item in items:
        caption = f"📦 {item['name']}\n💰 Цена: {item['price']}\n📏 Размеры: {item['sizes']}"
        kb = [[InlineKeyboardButton("Заказать", callback_data=f"buy_{item['id']}")]]
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=item['photo_id'], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    return MENU

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split('_')[1]
    context.user_data['buy_id'] = item_id
    await context.bot.send_message(chat_id=query.message.chat_id, text="Шаг 1/3: Отправьте размер:")
    return CAT_1

async def buy_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_size'] = update.message.text
    await update.message.reply_text("Шаг 2/3: Отправьте цвет / комментарий:")
    return CAT_2

async def buy_step_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_comment'] = update.message.text
    await update.message.reply_text("Шаг 3/3: Отправьте контактные данные / адрес:")
    return CAT_3

async def buy_step_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text
    user = update.effective_user
    items = load_data(CATALOG_FILE)
    item_name = next((i['name'] for i in items if str(i['id']) == str(context.user_data['buy_id'])), "Unknown")
    
    order = {
        "type": "catalog",
        "user_id": user.id,
        "product": item_name,
        "messages": [context.user_data['buy_size'], context.user_data['buy_comment'], contact]
    }
    orders = load_data(ORDERS_FILE)
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    
    admin_msg = f"🛍️ НОВЫЙ ЗАКАЗ (КАТАЛОГ)\nТовар: {item_name}\nОт: {user.id}\n1: {order['messages'][0]}\n2: {order['messages'][1]}\n3: {order['messages'][2]}"
    await context.bot.send_message(chat_id=OWNER_ID, text=admin_msg)
    
    await update.message.reply_text("✅ Заказ оформлен!")
    return await start(update, context)

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Опишите вашу проблему в одном сообщении:")
    return SUPPORT

async def support_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text
    await context.bot.send_message(chat_id=OWNER_ID, text=f"💬 ТЕХПОДДЕРЖКА\nОт: {user_id}\nСообщение: {msg}")
    await update.message.reply_text("Ваше сообщение отправлено поддержке.")
    return await start(update, context)

async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("1) Отправьте фото товара:")
    return ADMIN_PHOTO

async def admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("2) Введите название:")
    return ADMIN_NAME

async def admin_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_name'] = update.message.text
    await update.message.reply_text("3) Введите цену:")
    return ADMIN_PRICE

async def admin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_price'] = update.message.text
    await update.message.reply_text("4) Введите размеры через запятую:")
    return ADMIN_SIZES

async def admin_sizes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = load_data(CATALOG_FILE)
    new_id = len(items) + 1
    new_item = {
        "id": new_id,
        "name": context.user_data['new_name'],
        "photo_id": context.user_data['new_photo'],
        "price": context.user_data['new_price'],
        "sizes": update.message.text
    }
    items.append(new_item)
    save_data(CATALOG_FILE, items)
    await update.message.reply_text("✅ Товар добавлен!")
    return await start(update, context)

async def admin_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    orders = load_data(ORDERS_FILE)
    if not orders:
        await update.callback_query.message.reply_text("Заказов нет.")
        return
    for o in orders:
        msg = f"Тип: {o['type']}\nUser: {o['user_id']}\nТовар: {o['product']}\nИнфо: {o['messages']}"
        await update.callback_query.message.reply_text(msg)

async def admin_del_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    items = load_data(CATALOG_FILE)
    if not items:
        await update.callback_query.edit_message_text("Каталог пуст.")
        return
    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(f"Удалить {i['name']}", callback_data=f"del_{i['id']}")])
    await update.callback_query.edit_message_text("Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split('_')[1])
    items = load_data(CATALOG_FILE)
    items = [i for i in items if i['id'] != item_id]
    save_data(CATALOG_FILE, items)
    await query.edit_message_text("Товар удален.")
    return await start(update, context)

if __name__ == "__main__":
    init_files()
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(order_link_start, pattern="^order_link$"),
            CallbackQueryHandler(catalog_list, pattern="^catalog_list$"),
            CallbackQueryHandler(support_start, pattern="^support$"),
            CallbackQueryHandler(buy_item, pattern="^buy_"),
            CallbackQueryHandler(admin_add_start, pattern="^admin_add$"),
            CallbackQueryHandler(admin_del_start, pattern="^admin_del$"),
        ],
        states={
            MENU: [CallbackQueryHandler(order_link_start, pattern="^order_link$"), CallbackQueryHandler(catalog_list, pattern="^catalog_list$"), CallbackQueryHandler(support_start, pattern="^support$")],
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
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_view_orders, pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(admin_del_confirm, pattern="^del_"))

    app.run_polling()
