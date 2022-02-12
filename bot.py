import csv
import logging
import os
import random
import uuid

from fuzzywuzzy import fuzz
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultCachedSticker,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    CallbackContext,
    ChosenInlineResultHandler,
    Filters,
    InlineQueryHandler,
    MessageHandler,
    Updater,
)

MINUTE = 60

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def load_db() -> dict[tuple[str, str], tuple[str]]:
    with open("stickers.csv", "r") as f:
        reader = csv.DictReader(f, ["id", "sticker_file_id"], restkey="search_tags")
        first_line = next(reader)
        if first_line.get("id") != "id":
            f.seek(0)

        return {
            (entry["id"], entry["sticker_file_id"]): tuple(entry["search_tags"])
            for entry in reader
        }


db = load_db()

inverted_db = {val: k for k, values in db.items() for val in values}
inverted_db_keys = inverted_db.keys()


def ranked_matches(query: str) -> set[tuple[str, str]]:
    match_ratio = 80

    return {
        inverted_db[key]
        for key, ratio in sorted(
            ((k, fuzz.partial_ratio(k, query)) for k in inverted_db_keys),
            key=lambda _: _[1],
            reverse=True,
        )
        if ratio >= match_ratio
    }


def inline_handler(update: Update, _):
    query = update.inline_query.query

    if query == "":
        matches = {inverted_db[key] for key in inverted_db_keys}
    else:
        matches = ranked_matches(query)

    if matches:
        update.inline_query.answer(
            [
                InlineQueryResultCachedSticker(id=match[0], sticker_file_id=match[1])
                for match in matches
            ],
            is_personal=False,
            auto_pagination=True,
            cache_time=60 * MINUTE,
        )
    else:
        update.inline_query.answer(
            [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Контора пидорасов",
                    input_message_content=InputTextMessageContent(
                        message_text=f"{query} - контора пидорасов"
                    ),
                )
            ],
            is_personal=False,
            auto_pagination=True,
        )


def echo_sticker(update: Update, _):
    update.message.reply_text(
        f"`{update.message.sticker.file_id}`", parse_mode="markdown"
    )


def echo_usage(update: Update, context: CallbackContext):
    update.message.reply_text(
        f"Попробуй что-н поискать, например: `{context.bot.bot.name} {random.choice(list(inverted_db_keys))}`",
        parse_mode="markdown",
    )


def echo(update: Update, _):
    logging.info(
        "[STICKER CHOSEN] query='%s' result='%s'",
        update.chosen_inline_result.query,
        update.chosen_inline_result.result_id,
    )


TG_TOKEN = os.getenv("TG_TOKEN")
updater = Updater(TG_TOKEN)

updater.dispatcher.add_handler(InlineQueryHandler(inline_handler))
updater.dispatcher.add_handler(MessageHandler(Filters.sticker, echo_sticker))
updater.dispatcher.add_handler(ChosenInlineResultHandler(echo))
updater.dispatcher.add_handler(MessageHandler(Filters.all, echo_usage))


if __name__ == "__main__":
    # updater.start_polling()
    PORT = int(os.getenv("PORT", 8080))
    APP_NAME = os.getenv("HEROKU_APP_NAME")
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TG_TOKEN,
        webhook_url=f"https://{APP_NAME}.herokuapp.com/{TG_TOKEN}",
    )
    updater.idle()
