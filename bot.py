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
        "Ты в *POIZON LAB* — мы помогаем заказать *оригинальную одежду и обувь* "
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
