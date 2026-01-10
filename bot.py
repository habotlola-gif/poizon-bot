import os
import json
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

# ================= FILE =================
CATALOG_FILE = "catalog.json"

# ================= STORAGE =================
CATALOG = []
CATALOG_ID = 1

ORDERS_LINK = []
ORDERS_CATALOG = []
SUPPORT_MESSAGES = []

# ================= LOAD / SAVE =================
def load_catalog():
    global CATALOG, CATALOG_ID
    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            CATALOG = data.get("items", [])
            CATALOG_ID = data.get("last_id", 1)

def save_catalog():
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"items": CATALOG, "last_id": CATALOG_ID},
            f,
            ensure_ascii=False,
            indent=2
        )

# ================= MENUS =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Заказать через ссылку", callback_data="order_link")],
        [InlineKeyboardButton("📦 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton("💬 Техподдержка", callback_data="support")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add_item")],
        [InlineKeyboardButton("❌ Удалить товар", callback_data="admin_delete_item")],
    ])

def catalog_menu():
    if not CATALOG:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("— каталог пуст —", callback_data="noop")]
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(item["name"], callback_data=f"catalog_item_{item['id']}")]
        for item in CATALOG
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

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 *Админ-панель*",
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # --- SUPPORT ---
    if query.data == "support":
        context.user_data.clear()
        context.user_data["state"] = "support"
        await query.message.reply_text(
            "💬 *Техподдержка*\n\n"
            "Опиши вопрос — мы ответим как можно быстрее 👌",
            parse_mode="Markdown"
        )

    # --- ORDER LINK ---
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
            "📏 размер\n"
            "🎨 цвет / комментарий\n\n"
            "После этого заказ будет принят ✅",
            parse_mode="Markdown"
        )

    # --- CATALOG ---
    elif query.data == "catalog":
        await query.message.reply_text(
            "📦 *Каталог товаров*",
            reply_markup=catalog_menu(),
            parse_mode="Markdown"
        )

    elif query.data.startswith("catalog_item_"):
        item_id = int(query.data.replace("catalog_item_", ""))
        item = next(i for i in CATALOG if i["id"] == item_id)

        context.user_data.clear()
        context.user_data.update({
            "state": "order_catalog",
            "product": item["name"],
            "count": 0,
            "messages": []
        })

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=item["photo_id"],
            caption=(
                f"📦 *{item['name']}*\n\n"
                f"💰 Цена: *{item['price']} ₽*\n"
                f"📏 Размеры: *{', '.join(item['sizes'])}*\n\n"
                "Отправь *3 сообщения* для заказа:\n"
                "📏 размер\n"
                "🎨 цвет\n"
                "✍️ комментарий"
            ),
            parse_mode="Markdown"
        )

# ================= ADMIN CALLBACKS =================
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "admin_add_item":
        context.user_data.clear()
        context.user_data["state"] = "admin_photo"
        await query.message.reply_text("📸 Отправь фото товара")

    elif query.data == "admin_delete_item":
        kb = [
            [InlineKeyboardButton(f"❌ {i['name']}", callback_data=f"del_{i['id']}")]
            for i in CATALOG
        ]
        await query.message.reply_text(
            "Выбери товар для удаления",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif query.data.startswith("del_"):
        item_id = int(query.data.replace("del_", ""))
        CATALOG[:] = [i for i in CATALOG if i["id"] != item_id]
        save_catalog()
        await query.message.reply_text("❌ Товар удалён")

# ================= MESSAGE HANDLER =================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CATALOG_ID

    uid = update.message.from_user.id
    text = update.message.text
    state = context.user_data.get("state")

    # --- ADMIN ADD FLOW ---
    if uid == ADMIN_ID:
        if state == "admin_photo" and update.message.photo:
            context.user_data["photo"] = update.message.photo[-1].file_id
            context.user_data["state"] = "admin_name"
            await update.message.reply_text("✍️ Название товара")
            return

        if state == "admin_name":
            context.user_data["name"] = text
            context.user_data["state"] = "admin_price"
            await update.message.reply_text("💰 Цена (числом, без ₽)")
            return

        if state == "admin_price":
            context.user_data["price"] = text
            context.user_data["state"] = "admin_sizes"
            await update.message.reply_text("📏 Размеры через запятую (пример: 40,41,42)")
            return

        if state == "admin_sizes":
            CATALOG.append({
                "id": CATALOG_ID,
                "name": context.user_data["name"],
                "photo_id": context.user_data["photo"],
                "price": context.user_data["price"],
                "sizes": [s.strip() for s in text.split(",")]
            })
            CATALOG_ID += 1
            save_catalog()
            context.user_data.clear()
            await update.message.reply_text("✅ Товар добавлен в каталог")
            return

    # --- SUPPORT ---
    if state == "support":
        SUPPORT_MESSAGES.append({"user_id": uid, "text": text})
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Техподдержка | user_id: {uid}\n\n{text}"
        )
        return

    # --- ORDERS ---
    if state in ("order_link", "order_catalog"):
        context.user_data["count"] += 1
        context.user_data["messages"].append(text)

        if context.user_data["count"] >= 3:
            await update.message.reply_text(
                "✅ *Заказ принят!*\n\nМы скоро свяжемся с тобой 👌",
                parse_mode="Markdown"
            )
            context.user_data.clear()
        return

# ================= MAIN =================
def main():
    load_catalog()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^(admin|del_)"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_messages))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
