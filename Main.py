import asyncio
import time
import traceback
from datetime import datetime
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from Audit import get_audit
from Bubble import run_bubble
from Chart import get_chart
from Copycat import run_copycat
from Database import setup_database
from Logs import log_info_main, log_action_main, log_divider_main, log_error_main
from Pro import run_pro, run_setWallet, isPremiumUser, HOME_WALLET
from Scan import run_scan
from Telegram import get_telegram_link
from Volume import get_all_volumes
from Web import get_website_link
from Bundle import get_bundle_sniping_insights
from Config import BOT_TOKEN
from Ai import run_ai
from Winrate import run_winrate

# Track users currently executing commands
processing_users = set()

# Global semaphore for limiting concurrent requests
rate_limiter = asyncio.Semaphore(30)

# Group rate-limiting storage
group_request_times = {}

pro_commands = ["copycat", "ai", "winrate", "virality", "x", "dev"]

async def check_group_rate_limit(chat_id: int) -> bool:
    """Check if a group has exceeded the allowed rate limit (20 requests per minute)."""
    current_time = time.time()

    if chat_id not in group_request_times:
        group_request_times[chat_id] = []

    # Remove requests older than 60 seconds
    group_request_times[chat_id] = [t for t in group_request_times[chat_id] if current_time - t < 60]

    # If the group has made 20 or more requests in the last 60 seconds, deny further requests
    if len(group_request_times[chat_id]) >= 20:
        return False

    # Log the current request time for the group
    group_request_times[chat_id].append(current_time)
    return True

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command_name: str, process_function, process_args=None):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or "Anonymous"

    # Prevent users from spamming multiple commands at once
    if user_id in processing_users:
        return

    log_divider_main(f"{command_name.upper()} COMMAND")
    log_action_main(f"{command_name.capitalize()} Command Received", f"User: {user_name} (ID: {user_id})")

    # Check group rate limit if in a group chat
    if chat_id < 0 and not await check_group_rate_limit(chat_id):
        return

    if context.args or command_name == "help" or command_name == "start":
        if command_name == "help" or command_name == "start":
            token_address = ""
        else:
            token_address = context.args[0]

        log_info_main(f"Processing {command_name.capitalize()} Command", f"Token Address: {token_address}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        if not await isPremiumUser(user_id) and command_name in pro_commands:
            return

        # Mark user as processing a command
        processing_users.add(user_id)

        if command_name in pro_commands and chat_id < 0:
            result = "Pro commands can only be used in private chats"
        else:
            result = await process_function(token_address, *(process_args or []))

        async with rate_limiter:
            if not result:
                await update.message.reply_text(
                    "❌ **Invalid Token Address**\n\n"
                    "Please check the token address and try again.",
                    parse_mode="Markdown",
                )
                log_error_main(f"{command_name.capitalize()} Command Failed", f"Token Address: {token_address}")
            else:
                if command_name.upper() == "BUBBLE" or command_name.upper() == "CHART":
                    # Check if the result is a message or an image
                    if isinstance(result, InputMediaPhoto):
                        try:
                            # Check if the result contains an InputFile object
                            media_file = result.media
                            # If it's an InputFile object, try to send it as a photo
                            await update.message.reply_photo(media_file)
                        except Exception as e:
                            log_error_main(f"{command_name.upper()} Command Failed", f"Error: {e}")
                            await update.message.reply_text("❌ **Error Sending Image**\n\nPlease try again later.")

                    else:
                        # If it's a message (string), send the message as a reply
                        await update.message.reply_text(result)
                else:
                    await update.message.reply_text(result, parse_mode="Markdown")
                log_info_main(f"{command_name.capitalize()} Result Sent", f"Token Address: {token_address}")

        # Remove typing action after sending the message
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="cancel")

    # Remove user from processing list after command execution
    processing_users.discard(user_id)
    log_divider_main("END COMMAND")


def measure_execution_time(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        start_time = datetime.now()
        try:
            await func(update, context)
        finally:
            elapsed_time = datetime.now() - start_time
            log_info_main("Execution Time", f"{func.__name__} took {elapsed_time.total_seconds():.2f} seconds")

    return wrapper


@measure_execution_time
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_start(token_address):
        try:
            return (
                "👋 **Welcome!**\n\n"
                "I'm your friendly bot, ready to assist you with various commands.\n"
                "Use `/help` to see all available commands. 😊"
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Start Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "start",
        process_start,
    )

@measure_execution_time
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_help(token_address):
        try:
            return (
                "🤖 **How to Use This Bot** 🤖\n\n"
                "**Step 1:** Choose a token and get its token address. 🔑\n"
                "  - You can find the token address from platforms like Pump.fun, Dexscreener, or any other source.\n\n"
                "**Step 2:** Choose a command based on the type of information you want. 🛠️\n"
                "  - See the list of available commands below to find what suits your needs.\n\n"
                "**Step 3:** Type `/command token_address` to use the bot. 💬\n"
                "  - Example: `/audit 0x12345abcde6789...`\n\n\n"
                "🎉 **FREE COMMANDS** 🎉\n\n"
                "/scan: 🔍 Overview of top wallets holding given token, their balances, percentage of supply, and other assets in each token account.\n\n"
                "/bundle: 🧳 Bundling summary for given pump.fun token, including total tokens bundled, number of wallets involved, and bundle breakdowns from the last 1000 transactions.\n\n"
                "/audit: 🔒 Detailed token audit with attributes like mintability, mutability, freezing status, LP burn, and ownership details.\n\n"
                "/bubble: 🗺️ Provides a visual representation of top 10 holders and token distribution.\n\n"
                "/volume: 📊 Provides trading volume snapshots in 5-minute, 1-hour, 6-hours, and 24-hour time frames.\n\n"
                "/dex: 📈 Links to token performance charts on Dexscreener.\n\n"
                "/chart: 📈 Provides a chart of the token's daily price performance over the last week.\n\n"
                "/web: 🌐 Fetches website info for given token.\n\n"
                "/telegram: 📱 Fetches Telegram link for given token.\n\n"
                "/setwallet: 🖋️ Set the wallet you will use to send the payment. **Expires every 30 minutes**\n\n"
                "/pro: 📝 Set the transaction signature of your payment so we can confirm it.\n\n\n"
                
                "🔑 To access premium features, please follow these steps: 🔑\n\n"
                "**Step 1:** Set the wallet you will pay from by typing `/setwallet <wallet address>`. (Note: This step expires in 30 minutes, so be sure to complete the next steps within that time.)\n\n"
                f"**Step 2:** Pay **1 SOL for 1 month access** to our wallet: `{HOME_WALLET}`. (Please account for any transaction fees.)\n\n"
                "**Step 3:** After payment, provide the transaction signature of your payment by typing `/pro <transaction signature>` so we can confirm your payment.\n\n\n"
                
                "💎 **PREMIUM COMMANDS** 💎\n\n"
                "/copycat: 🕵️‍♂️ Identifies if a coin already exists or is unique.\n\n"
                "/ai: 🤖 Summarizes wallet analysis, win rates, and confidence levels, with average wallet profit metrics.\n\n"
                "/winrate: 🔥 Advanced breakdown of top-performing wallets and their trade histories.\n"
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Help Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "help",
        process_help,
    )


@measure_execution_time
async def audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_audit(token_address):
        try:
            result = await get_audit(token_address)
            return (
                f"🎉 **Audit Complete!**\n\nHere are the results for: `{token_address}`\n\n{result}"
                if result
                else None
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Audit Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "audit",
        process_audit,
    )


@measure_execution_time
async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_volume(token_address):
        try:
            result = await get_all_volumes(token_address)
            return (
                f"🎉 **Volume Data Retrieved!**\n\nHere are the volume details for: `{token_address}`\n\n{result}"
                if result != "Invalid token Address"
                else None
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Volume Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "volume",
        process_volume,
    )

@measure_execution_time
async def dex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_dex(token_address):
        try:
            return f"🎉 **Dex Link Ready!**\n\nHere is your Dex link for: `{token_address}`\n\nhttps://dexscreener.com/solana/{token_address}"

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Dex Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "dex",
        process_dex,
    )

@measure_execution_time
async def bubble(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_bubble(token_address):
        try:
            image_buffer = await run_bubble(token_address)
            return InputMediaPhoto(media=image_buffer) if image_buffer else None

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Bubble Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "bubble",
        process_bubble,
    )

@measure_execution_time
async def telegram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_telegram(token_address):
        try:
            telegram_link = await get_telegram_link(token_address)
            if telegram_link == "Invalid token Address":
                return "No Telegram Link Found"
            return f"🎉 **Telegram Link Retrieved!**\n\nHere is the Telegram link for: `{token_address}`\n\n{telegram_link}"


        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Telegram Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "telegram",
        process_telegram,
    )

@measure_execution_time
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_scan(token_address):
        try:
            scan_result = await run_scan(token_address)
            return (
                f"🎉 **Scan Complete!**\n\nHere are the results for: `{token_address}`\n\n{scan_result}"
                if scan_result
                else None
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Scan Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "scan",
        process_scan,
    )


@measure_execution_time
async def bundle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_bundle(token_address):
        try:
            insights = await get_bundle_sniping_insights(token_address)
            return f"🎉 **Bundle Insights:**\n\n{insights}" if insights else None

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Bundle Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "bundle",
        process_bundle,
    )


@measure_execution_time
async def web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_web(token_address):
        try:
            website_link = await get_website_link(token_address)
            if website_link == "Invalid token Address":
                return None
            elif website_link == "No Website link found.":
                return "❌ **No Website Link Found**\n\n"
            return f"🎉 **Website Link Retrieved!**\n\nHere is the link for: `{token_address}`\n\n{website_link}"


        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Web Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "web",
        process_web,
    )


@measure_execution_time
async def copycat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_copycat(token_address):
        try:
            result = await run_copycat(token_address)
            return f"🎉 **Copycat Analysis Result:**\n\n{result}" if result else None

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Copycat Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "copycat",
        process_copycat,
    )

@measure_execution_time
async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_ai(token_address):
        try:
            result = await run_ai(token_address)
            return (
                f"🎉 **AI Data Retrieved!**\n\nHere are the AI details for: `{token_address}`\n\n{result}"
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"AI Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "ai",
        process_ai,
    )

@measure_execution_time
async def winrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_winrate(token_address):
        try:
            result = await run_winrate(token_address)
            return (
                f"🎉 **Winrate Data Retrieved!**\n\nHere are the winrate details for: `{token_address}`\n\n{result}"
            )

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Winrate Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "winrate",
        process_winrate,
    )

@measure_execution_time
async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_chart(token_address):
        try:
            image_buffer = await get_chart(token_address)
            if not image_buffer:
                return "Something went wrong"
            if not isinstance(image_buffer, str):
                return InputMediaPhoto(media=image_buffer)
            else:
                return image_buffer


        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Chart Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "chart",
        process_chart,
    )


@measure_execution_time
async def pro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_pro(transaction_sig):
        try:
            user_id = update.effective_user.id
            result = await run_pro(transaction_sig, user_id)
            return result

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"Pro Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "pro",
        process_pro,
    )


@measure_execution_time
async def setWallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async def process_setWallet(wallet_address):
        try:
            user_id = update.effective_user.id
            result = await run_setWallet(wallet_address, user_id)
            return result

        except Exception as e:
            error_details = traceback.format_exc()
            log_error_main(f"SetWallet Command Failed", f"Error: {e}, Details: {error_details}")
            return (
                "❌ **Error Occurred**\n\n"
                "An error occurred while processing your request. Please try again later. 🙁",
            )

    await handle_command(
        update,
        context,
        "setwallet",
        process_setWallet,
    )


def run_bot():
    """Run the bot."""
    log_divider_main("STARTING BOT")
    log_action_main("Initializing Bot")

    # Build application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    log_info_main("Registering Command Handlers")
    commands = {
        'start': start,
        'help': help,
        'audit': audit,
        'volume': volume,
        'dex': dex,
        'bubble': bubble,
        'telegram': telegram,
        'web': web,
        'scan': scan,
        'bundle': bundle,
        'copycat': copycat,
        'winrate': winrate,
        'ai': ai,
        'chart': chart,
        'pro': pro,
        'setwallet': setWallet
    }

    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler, block=False))

    # Add message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    log_info_main("Command Handlers Registered Successfully")
    log_divider_main("BOT RUNNING")

    # Start the bot
    application.run_polling(allowed_updates=["message", "edited_message"])


if __name__ == '__main__':
    try:
        setup_database()
        run_bot()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc().print_exc()