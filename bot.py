import os
import logging
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# 开启日志，方便查看错误
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# 从环境变量读取密钥（部署时设置，绝不写死在代码里）
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 初始化 OpenAI 客户端
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- 付费系统简易版（内存存储，重启会清空，但适合起步）----------
# 用户使用次数记录：{user_id: 使用次数}
user_usage = {}
# 有效激活码集合（通过 /redeem 激活后可无限使用）
valid_codes = {"FREE2026", "VIP2026"}   # 你可以换成自己生成的码，或者从数据库读取
vip_users = set()

# 免费试用次数上限
FREE_LIMIT = 3

def is_vip(user_id):
    return user_id in vip_users

def can_use(user_id):
    if is_vip(user_id):
        return True
    return user_usage.get(user_id, 0) < FREE_LIMIT

# ---------- 机器人命令 ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 欢迎使用 AI 图像生成机器人！\n"
        "发送描述文字即可生成图片，例如：`一只在太空漂浮的柴犬`\n"
        f"新用户免费 {FREE_LIMIT} 次，之后需要输入激活码。\n"
        "使用 /redeem <激活码> 激活无限使用。"
    )

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_vip(user_id):
        await update.message.reply_text("你已经是VIP了，无需再次激活。")
        return

    try:
        code = context.args[0]
    except IndexError:
        await update.message.reply_text("使用方法：/redeem 激活码")
        return

    if code in valid_codes:
        vip_users.add(user_id)
        await update.message.reply_text("✅ 激活成功！你现在可以无限使用图像生成。")
    else:
        await update.message.reply_text("❌ 激活码无效，请检查后重试。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = update.message.text

    if not can_use(user_id):
        await update.message.reply_text(
            f"你的免费次数已用完（{FREE_LIMIT}次），请使用 /redeem 激活码 激活无限使用。\n"
            "购买激活码请联系 @YourSupportUsername"
        )
        return

    # 通知用户正在生成
    msg = await update.message.reply_text("正在为你创作，请稍候...")

    try:
        # 调用 OpenAI 图像生成 API（DALL-E 3）
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        # 发送图片
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url)
        # 更新使用次数
        if not is_vip(user_id):
            user_usage[user_id] = user_usage.get(user_id, 0) + 1
        # 删除“正在创作”消息
        await msg.delete()
    except Exception as e:
        logging.error(f"图像生成失败: {e}")
        await msg.edit_text("生成失败，请稍后重试或检查描述是否违规。")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

# ---------- 主程序 ----------
def main():
    # 创建应用
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # 注册命令处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("redeem", redeem))
    # 注册普通文字消息处理器
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    # 启动轮询
    print("机器人已启动...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()