import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= ENV =================
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMIN_ID = OWNER_ID

# ================= STORAGE =================
ORDERS_LINK = []
ORDERS_CATALOG = []
SUPPORT_MESSAGES = []

# ================= MENUS =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Заказать через ссылку", callback_data="order_link")],
        [InlineKeyboardButton("📦 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton("💬 Техподдержка", callback_data="support")],
    ])

def catalog_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👟 Кроссовки", callback_data="catalog_sneakers")],
        [InlineKeyboardButton("👕 Одежда", callback_data="catalog_clothes")],
        [InlineKeyboardButton("🎒 Аксессуары", callback_data="catalog_accessories")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Заказы по ссылке", callback_data="admin_orders_link")],
        [InlineKeyboardButton("🛍 Заказы из каталога", callback_data="admin_orders_catalog")],
        [InlineKeyboardButton("💬 Техподдержка", callback_data="admin_support")],
    ])

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 *Привет!*\n\n"
        "Ты в *POIZON LAB* — помогаем заказать *оригинальную одежду и обувь* "
        "с платформы POIZON 🇨🇳\n\n"
        "Выбери, что хочешь сделать 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 *Админ-панель POIZON LAB*\n\n"
        "Выбери нужный раздел 👇",
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "support":
        context.user_data.clear()
        context.user_data["state"] = "support"
        await query.message.reply_text(
            "💬 *Техподдержка POIZON LAB*\n\n"
            "Опиши свой вопрос — сообщение будет передано администратору 👨‍💻",
            parse_mode="Markdown"
        )

    elif query.data == "order_link":
        context.user_data.clear()
        context.user_data.update({
            "state": "order_link",
            "count": 0,
            "messages": []
        })
        await query.message.reply_text(
            "🛒 *Заказ через ссылку*\n\n"
            "Отправь *3 сообщения*:\n"
            "🔗 ссылку на товар\n"
            "📏 размер / цвет\n"
            "✍️ комментарий (если есть)\n\n"
            "После этого заказ автоматически закроется ✅",
            parse_mode="Markdown"
        )

    elif query.data == "catalog":
        await query.message.reply_text(
            "📦 *Каталог товаров*\n\n"
            "Выбери категорию 👇",
            reply_markup=catalog_menu(),
            parse_mode="Markdown"
        )

    elif query.data.startswith("catalog_"):
        product = query.data.replace("catalog_", "")
        context.user_data.clear()
        context.user_data.update({
            "state": "order_catalog",
            "product": product,
            "count": 0,
            "messages": []
        })
        await query.message.reply_text(
            f"📦 *Выбран товар:* {product}\n\n"
            "Отправь *3 сообщения* для оформления заказа ✍️",
            parse_mode="Markdown"
        )

# ================= ADMIN CALLBACKS =================
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "admin_orders_link":
        text = "📦 *Заказы по ссылке*\n\n"
        if not ORDERS_LINK:
            text += "— пока пусто —"
        else:
            for o in ORDERS_LINK:
                text += f"user_id: {o['user_id']}\n"
                for m in o["messages"]:
                    text += f"• {m}\n"
                text += "\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "admin_orders_catalog":
        text = "🛍 *Заказы из каталога*\n\n"
        if not ORDERS_CATALOG:
            text += "— пока пусто —"
        else:
            for o in ORDERS_CATALOG:
                text += f"Товар: {o['product']}\nuser_id: {o['user_id']}\n"
                for m in o["messages"]:
                    text += f"• {m}\n"
                text += "\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "admin_support":
        text = "💬 *Сообщения техподдержки*\n\n"
        if not SUPPORT_MESSAGES:
            text += "— пока пусто —"
        else:
            for s in SUPPORT_MESSAGES:
                text += f"user_id: {s['user_id']}\n{s['text']}\n\n"
        await query.message.reply_text(text, parse_mode="Markdown")

# ================= MESSAGE HANDLER =================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text
    state = context.user_data.get("state")

    # --- SUPPORT ---
    if state == "support":
        SUPPORT_MESSAGES.append({
            "user_id": uid,
            "text": text
        })
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Техподдержка\nuser_id: {uid}\n\n{text}"
        )
        return

    # --- ORDERS ---
    if state in ("order_link", "order_catalog"):
        context.user_data["count"] += 1
        context.user_data["messages"].append(text)
        count = context.user_data["count"]

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 {'Заказ через ссылку' if state == 'order_link' else 'Заказ из каталога'}\n"
                 f"{count}/3\nuser_id: {uid}\n\n{text}"
        )

        if count >= 3:
            if state == "order_link":
                ORDERS_LINK.append({
                    "user_id": uid,
                    "messages": context.user_data["messages"]
                })
            else:
                ORDERS_CATALOG.append({
                    "user_id": uid,
                    "product": context.user_data["product"],
                    "messages": context.user_data["messages"]
                })

            await update.message.reply_text(
                "✅ *Заказ принят!*\n\n"
                "Мы свяжемся с тобой после проверки товара 👌",
                parse_mode="Markdown"
            )
            context.user_data.clear()
        return

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
