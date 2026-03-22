'''
This program requires the following modules:
- python-telegram-bot==22.5
- urllib3==2.6.2
- pymongo[srv]
- requests
'''
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import configparser
import logging
from ChatGPT import ChatGPT
from db import MongoLogger

gpt = None
mongo_logger = None


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    logging.info('INIT: Loading configuration...')
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    global gpt
    global mongo_logger
    gpt = ChatGPT(config)
    mongo_logger = MongoLogger(config)

    logging.info('INIT: Connecting the Telegram bot...')
    app = ApplicationBuilder().token(
        config['TELEGRAM']['ACCESS_TOKEN']
    ).build()

    logging.info('INIT: Registering handlers...')
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myinterests", my_interests_command))
    app.add_handler(CommandHandler("findmatches", find_matches_command))
    app.add_handler(CommandHandler("events", events_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback))

    logging.info('INIT: Initialization done!')
    app.run_polling()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Hello! I am your campus assistant bot.\n\n"
        "Available features:\n"
        "1. Interest matching\n"
        "   Send: interest: AI, robotics, data science\n"
        "2. Event recommendation\n"
        "   Use command: /events\n"
        "3. View your interests\n"
        "   Use command: /myinterests\n"
        "4. Find similar users\n"
        "   Use command: /findmatches\n\n"
        "You can also chat with me normally."
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Usage:\n"
        "- Register interests:\n"
        "  interest: AI, machine learning, cybersecurity\n\n"
        "- View your interests:\n"
        "  /myinterests\n\n"
        "- Find users with similar interests:\n"
        "  /findmatches\n\n"
        "- Get event recommendations:\n"
        "  /events"
    )
    await update.message.reply_text(text)


async def my_interests_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else "unknown"
    interests = mongo_logger.get_user_interests(user_id)

    if not interests:
        await update.message.reply_text(
            "You have not saved any interests yet.\n"
            "Example:\ninterest: AI, robotics, data science"
        )
        return

    await update.message.reply_text(
        "Your saved interests are:\n- " + "\n- ".join(interests)
    )


async def find_matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user else "unknown"

    interests = mongo_logger.get_user_interests(user_id)
    if not interests:
        await update.message.reply_text(
            "You need to save your interests first.\n"
            "Example:\ninterest: AI, robotics, data science"
        )
        return

    matches = mongo_logger.find_matching_users(user_id, interests)

    if not matches:
        await update.message.reply_text(
            "No similar users found yet. Try again later after more users register interests."
        )
        return

    lines = ["Users with similar interests:"]
    for m in matches:
        name = m.get("username") or "unknown_user"
        overlap = m.get("matched_interests", [])
        lines.append(f"- {name} | common interests: {', '.join(overlap)}")

    reply = "\n".join(lines)
    await update.message.reply_text(reply)

    mongo_logger.log_chat(
        user_id=user_id,
        username=username,
        user_message="/findmatches",
        bot_response=reply,
        feature="interest_matching"
    )


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user else "unknown"

    interests = mongo_logger.get_user_interests(user_id)

    if interests:
        prompt = (
            "Recommend 3 online or campus activities/events for a university student "
            f"who is interested in: {', '.join(interests)}. "
            "Format the answer as a short bullet list. "
            "Do not invent exact real-world dates or venues if unknown. "
            "You may suggest realistic types of events, workshops, meetups, study groups, or hackathons."
        )
    else:
        prompt = (
            "Recommend 3 general online or campus activities/events for a university student. "
            "Format the answer as a short bullet list. "
            "Do not invent exact real-world dates or venues if unknown."
        )

    loading_message = await update.message.reply_text('Generating event recommendations...')

    try:
        response = gpt.submit(prompt)

        mongo_logger.log_chat(
            user_id=user_id,
            username=username,
            user_message="/events",
            bot_response=response,
            feature="event_recommendation"
        )

        await loading_message.edit_text(response)

    except Exception as e:
        logging.exception("ERROR in /events")

        mongo_logger.log_chat(
            user_id=user_id,
            username=username,
            user_message="/events",
            bot_response="",
            status="error",
            error_message=str(e),
            feature="event_recommendation"
        )

        await loading_message.edit_text(f"Sorry, an error occurred: {str(e)}")


def parse_interests(user_text: str):
    """
    Example supported formats:
    interest: AI, robotics, data science
    interests: AI, cybersecurity
    """
    prefix_candidates = ["interest:", "interests:"]
    lower_text = user_text.lower()

    for prefix in prefix_candidates:
        if lower_text.startswith(prefix):
            raw = user_text[len(prefix):].strip()
            if not raw:
                return []

            items = [x.strip() for x in raw.split(",")]
            items = [x for x in items if x]
            # lowercase normalize + remove duplicates while keeping order
            normalized = []
            seen = set()
            for item in items:
                item_norm = item.lower()
                if item_norm not in seen:
                    seen.add(item_norm)
                    normalized.append(item_norm)
            return normalized

    return []


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("UPDATE: " + str(update))

    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user else "unknown"

    # Feature 1: save user interests
    interests = parse_interests(user_text)
    if interests:
        mongo_logger.save_user_interests(user_id, username, interests)

        reply = (
            "Your interests have been saved:\n- " + "\n- ".join(interests) +
            "\n\nUse /findmatches to find similar users.\n"
            "Use /events to get recommendations."
        )

        mongo_logger.log_chat(
            user_id=user_id,
            username=username,
            user_message=user_text,
            bot_response=reply,
            feature="interest_registration"
        )

        await update.message.reply_text(reply)
        return

    loading_message = await update.message.reply_text('Thinking...')

    try:
        response = gpt.submit(user_text)

        mongo_logger.log_chat(
            user_id=user_id,
            username=username,
            user_message=user_text,
            bot_response=response,
            feature="general_chat"
        )

        await loading_message.edit_text(response)

    except Exception as e:
        logging.exception("ERROR while processing message")

        mongo_logger.log_chat(
            user_id=user_id,
            username=username,
            user_message=user_text,
            bot_response="",
            status="error",
            error_message=str(e),
            feature="general_chat"
        )

        await loading_message.edit_text(f"Sorry, an error occurred: {str(e)}")


if __name__ == '__main__':
    main()