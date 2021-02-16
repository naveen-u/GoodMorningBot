import json
import logging
import os
import random
import re
import textwrap
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Callable, List, NamedTuple, Tuple

import dotenv
import requests
import telegram
from PIL import Image, ImageDraw, ImageFont
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update

# ---------------------------------------------------------------------------- #
#                                 Configuration                                #
# ---------------------------------------------------------------------------- #

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger()

dotenv.load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

FONT_OPTIONS = [f"fonts/{font}" for font in os.listdir("./fonts")]

COLOR_OPTIONS = [
    "yellow",
    "gold",
    "springgreen",
    "magenta",
    "orangered",
    "red",
    "cyan",
    "white",
]


class RegexInfo(NamedTuple):
    regex: str
    options: int


BLACKLISTED_REGEXES: List[RegexInfo] = [
    RegexInfo(r"\bI\b", 0),
    RegexInfo(r"\bm[ey]\b", re.IGNORECASE),
]

IST = timezone(timedelta(hours=5, minutes=30))

updater = Updater(token=TELEGRAM_TOKEN)
job_queue = updater.job_queue
dispatcher = updater.dispatcher


# ---------------------------------------------------------------------------- #
#                                 Greet command                                #
# ---------------------------------------------------------------------------- #


def greet(update: Update, context: CallbackContext):
    """Create a WhatsApp family group-style forward image
    with a quote and the given greeting.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update
    """
    greeting_made = False
    retries = 0
    while not greeting_made and retries <= 3:
        try:
            quote = get_random_quote()
            message = ""
            if context.args is not None:
                message = " ".join(context.args)
            if message.strip() == "":
                message = "Good Morning!"
            image = make_greeting(quote.strip(), message.strip())
            greeting_made = True
        except:
            print("Oops! Something bad happened. Retrying...")
    if greeting_made:
        context.bot.send_photo(chat_id=update.effective_chat.id, photo=image)
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, something seems to have gone wrong.",
        )


def get_random_quote() -> str:
    """Retrieve a random quote from the Forismatic API.

    Returns:
        str: The retrieved quote
    """
    quote = ""
    while quote == "":
        response = requests.get(
            "http://api.forismatic.com/api/1.0/?method=getQuote&lang=en&format=json"
        )
        if response.status_code != 200:
            print(f"Error while getting image: {response}")
            continue
        try:
            response_json = json.loads(response.text.replace("\\'", "'"))
        except json.decoder.JSONDecodeError as error:
            print(f"Error while decoding JSON: {response.text}\n{error}")
            continue
        quote_text: str = response_json["quoteText"]
        if contains_no_blacklisted_regexes(quote_text):
            quote = quote_text
    return quote


def contains_no_blacklisted_regexes(quote: str) -> bool:
    """Checks that the given string does not contain any of the blacklisted regex patterns.

    Args:
        quote (str): Quote to check

    Returns:
        bool: true if no backlisted patterns are present; false otherwise
    """
    return all(
        re.search(regex_info.regex, quote, regex_info.options) is None
        for regex_info in BLACKLISTED_REGEXES
    )


def make_greeting(quote: str, greeting: str) -> BytesIO:
    """Create a greeting image with the given quote and greeting.

    Args:
        quote (str): Quote to be put on the image
        greeting (str): Greeting message to be put on the image

    Returns:
        BytesIO: A byte stream with the created image
    """
    image = Image.open(
        requests.get("http://placeimg.com/400/300/nature", stream=True).raw
    )
    draw = ImageDraw.Draw(image)

    quote_font_family, greeting_font_family = pick_random_fonts()

    (quote_text, greeting_text) = adjust_line_breaks(
        quote_font_family, greeting_font_family, quote, greeting, image.width
    )
    quote_font = fit_text_in_image(
        quote_font_family, quote_text, image.height / 2, image.width
    )
    greeting_font = fit_text_in_image(
        greeting_font_family, greeting_text, image.height / 2, image.width
    )

    draw_text_on_image(
        draw, quote_text, quote_font, image.height / 2, image.width, 0, 0
    )

    draw_text_on_image(
        draw,
        greeting_text,
        greeting_font,
        image.height / 2,
        image.width,
        image.height / 2,
        0,
    )

    bio = BytesIO()
    bio.name = "image.jpeg"
    image.save(bio, "JPEG")
    bio.seek(0)
    return bio


def pick_random_fonts() -> Tuple[str, str]:
    """Randomly picks two fonts from the available options.

    Returns:
        Tuple[str, str]: A tuple containing two randomly selected fonts
    """
    quote_font_family = random.choice(FONT_OPTIONS)
    greeting_font_family = random.choice(FONT_OPTIONS)
    return quote_font_family, greeting_font_family


def adjust_line_breaks(
    quote_font_family: str,
    greeting_font_family: str,
    quote: str,
    greeting: str,
    width: int,
) -> Tuple[str, str]:
    """Adjusts the line breaks of the mutliline text so that proportion is maintained.

    Args:
        quote_font_family (str): Font family for the quote string
        greeting_font_family (str): Font family for the greeting text
        quote (str): The quote
        greeting (str): The greeting message
        width (int): Width of final multiline text

    Returns:
        Tuple[str, str]: A tuple containing quote and greeting texts
    """
    fontsize = 1
    quote_text = quote
    greeting_text = greeting
    quote_font = ImageFont.truetype(quote_font_family, fontsize)
    greeting_font = ImageFont.truetype(greeting_font_family, fontsize)

    while (
        not 0.5
        < text_dimensions_ratio(quote_font, greeting_font, quote_text, greeting_text)
        < 2
    ) and width > 1:
        width = width - 1
        quote_text = wrap_text(quote_font, quote, width)
        greeting_text = wrap_text(greeting_font, greeting, width)

    return quote_text, greeting_text


def wrap_text(font: ImageFont, text: str, width: int) -> str:
    """Wraps the given text according to the font and width provided.

    Args:
        font (ImageFont): Font being used
        text (str): Text to wrap
        width (int): Width in which text needs to be wrapped

    Returns:
        str: Wrapped text
    """
    w = (len(text) * width) // font.getsize(text)[0]
    return "\n".join(textwrap.wrap(text, w))


def text_dimensions_ratio(
    quote_font: ImageFont, greeting_font: ImageFont, quote_text: str, greeting_text: str
) -> float:
    """Get the ratio of the text's dimensions.

    Args:
        quote_font (ImageFont): Font used for the quote
        greeting_font (ImageFont): Font used for the greeting
        quote_text (str): The quote text
        greeting_text (str): The greeting message

    Returns:
        float: Ratio of total height to width of the text
    """
    return (
        quote_font.getsize_multiline(quote_text)[1]
        + greeting_font.getsize_multiline(greeting_text)[1]
    ) / (
        quote_font.getsize_multiline(quote_text)[0]
        + greeting_font.getsize_multiline(greeting_text)[0]
    )


def fit_text_in_image(
    font_family: str, text: str, height: int, width: int
) -> ImageFont:
    """Adjust the font such that the text fits in the image.

    Args:
        font_family (str): Font family
        text (str): Text to fit
        height (int): Height
        width (int): Width

    Returns:
        ImageFont: Font object with appropriate sizing
    """
    fontsize = 10
    font = ImageFont.truetype(font_family, fontsize)
    while font.getsize_multiline(text, spacing=10)[0] < 0.9 * width:
        fontsize += 1
        font = ImageFont.truetype(font_family, fontsize)

    while font.getsize_multiline(text, spacing=10)[0] > 0.9 * width:
        fontsize -= 1
        font = ImageFont.truetype(font_family, fontsize)

    while font.getsize_multiline(text, spacing=10)[1] > 0.8 * height:
        fontsize -= 1
        font = ImageFont.truetype(font_family, fontsize)
    return font


def draw_text_on_image(
    draw: ImageDraw,
    text: str,
    font: ImageFont,
    height: int,
    width: int,
    heigh_offset: int,
    width_offset: int,
):
    """Draw given text on the given image.

    Args:
        draw (ImageDraw): The ImageDraw object using which text will be drawn
        text (str): Text to draw on the image
        font (ImageFont): Font to be used
        height (int): Height of the image
        width (int): Width of the image
        heigh_offset (int): Height offset from the centre
        width_offset (int): Width offset from the centre
    """
    w, h = draw.multiline_textsize(text, font, spacing=10)
    left = width_offset + ((width - w) * 0.5)
    top = heigh_offset + ((height - h) * 0.5)

    draw.text(
        (left, top),
        text,
        random.choice(COLOR_OPTIONS),
        font=font,
        spacing=10,
        stroke_width=3,
        stroke_fill="black",
    )


# ---------------------------------------------------------------------------- #
#                               Schedule command                               #
# ---------------------------------------------------------------------------- #

MESSAGE, INTERVAL, FIRST, LAST, CREATOR = range(5)


def get_callback(message: str, chat_id: int) -> Callable[["CallbackContext"], None]:
    """Get the callback for scheduled greetings.

    Args:
        message (str): Greeting message to be sent
        chat_id (int): Chat to send the greeting to

    Returns:
        Callable: The callback to be passed to the job queue
    """

    def schedule_callback(context: CallbackContext):
        """Send a Happy Birthday greeting to the channel.

        Args:
            context (CallbackContext): CallbackContext for the update
        """
        greeting_made = False
        retries = 0
        while not greeting_made and retries <= 3:
            try:
                quote = get_random_quote()
                image = make_greeting(quote.strip(), message.strip())
                greeting_made = True
            except:
                print("Oops! Something bad happened. Retrying...")
                retries += 1
        if greeting_made:
            context.bot.send_photo(chat_id=chat_id, photo=image)
        else:
            print(f"Skipping scheduled message after {retries} retries.")

    return schedule_callback


def schedule(update: Update, context: CallbackContext) -> int:
    """Schedule a greeting to be sent at regular intervals.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation
    """
    user = update.message.from_user
    logger.info(f"Got a schedule request from {user.last_name}, {user.first_name}")
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nHow are you? Myself GoodMorningBot from The Internet. Actually, "
        + "I need a little more information to schedule your greeting. Kindly send *the "
        + "greeting message* you'd like me to schedule. Hoping for a fast response.\n\n"
        + "Thank you and regards,\nGoodMorningBot",
        parse_mode="markdown",
    )

    return MESSAGE


def schedule_message(update: Update, context: CallbackContext) -> int:
    """Process the greeting message to be scheduled.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation
    """
    context.user_data[MESSAGE] = update.message.text
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nThanks for sending me the greeting message. "
        + "I also need *the interval (in seconds)* at which you want to send the above-mentioned "
        + "greeting. Please type in that as well. Hoping for a quick reply.\n\n"
        + "With warmest regards,\nGoodMorningBot",
        parse_mode="markdown",
    )

    return INTERVAL


def schedule_interval(update: Update, context: CallbackContext) -> int:
    """Process the interval at which the message is to be scheduled.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation
    """
    context.user_data[INTERVAL] = int(update.message.text)
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nThank you for sending the interval data. When should I start sending "
        + "these greeting messages? Please give me *the start date and time in the yyyy-mm-dd HH:MM:SS format* "
        + " and I will start sending it then. Or if you want me to start now itself, reply 'now'.\n\n"
        + "With warmest regards,\nGoodMorningBot",
        parse_mode="markdown",
    )

    return FIRST


def schedule_first(update: Update, context: CallbackContext) -> int:
    """Process the start datetime to schedule the message from.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation
    """
    if update.message.text.lower() == "now":
        date_object = None
    else:
        try:
            date_object = datetime.strptime(update.message.text, "%Y-%m-%d %H:%M:%S")
            date_object = date_object.replace(tzinfo=IST)
            if date_object < datetime.now(IST):
                update.message.reply_text(
                    "Hello Respected Sir/Madamji,\n\nI am only a simple bot. I cannot do this time-travel stuffs. "
                    + "So kindly give me a date and time in the future only. "
                    + "Or if you want to schedule it immediately, reply 'now'. "
                    + "Hoping for a fast (and correct) reply.\n\n"
                    + "With fewer and fewer regards,\nGoodMorningBot",
                    parse_mode="markdown",
                )
            return FIRST
        except ValueError:
            update.message.reply_text(
                "Hello Respected Sir/Madamji,\n\nI _specifically_ mentioned one format no? Still why are you doing "
                + "such stupid things. Please please please give me a date and time in the yyyy-mm-dd HH:MM:SS format only. "
                + "Or if you want to schedule it immediately, reply 'now'. "
                + "Hoping for a fast (and correct) reply.\n\n"
                + "With fewer and fewer regards,\nGoodMorningBot",
                parse_mode="markdown",
            )
            return FIRST
    context.user_data[FIRST] = date_object
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nThank you for sending the start date. Please give me an *end date* also. "
        + "Use the same yyyy-mm-dd HH:MM:SS format again. Or if you want it to keep going forever, reply 'never'.\n\n"
        + "God bless,\nGoodMorningBot",
        parse_mode="markdown",
    )

    return LAST


def schedule_last(update: Update, context: CallbackContext) -> int:
    """Process the end datetime to schedule the message till.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation
    """
    if update.message.text.lower() == "never":
        date_object = None
    else:
        try:
            date_object = datetime.strptime(update.message.text, "%Y-%m-%d %H:%M:%S")
            date_object = date_object.replace(tzinfo=IST)
            if context.user_data[FIRST] is None and date_object < datetime.now(IST):
                update.message.reply_text(
                    "Hello Respected Sir/Madamji,\n\nI am only a simple bot. I cannot do this time-travel stuffs. "
                    + "So kindly give me a date and time in the future only. "
                    + "Or if you want it to repeat forever and ever and ever, reply 'never'. "
                    + "Hoping for a fast (and correct) reply.\n\n"
                    + "With fewer and fewer regards,\nGoodMorningBot",
                    parse_mode="markdown",
                )
                return LAST
            elif (
                context.user_data[FIRST] is not None
                and date_object < context.user_data[FIRST]
            ):
                update.message.reply_text(
                    "Hello Respected Sir/Madamji,\n\nWhat is this stupidity you are attempting? "
                    + "Kindly give me a date and time _after_ the start date. "
                    + "Or if you want it to repeat forever and ever and ever, reply 'never'. "
                    + "Hoping for a fast (and correct) reply.\n\n"
                    + "With fewer and fewer regards,\nGoodMorningBot",
                    parse_mode="markdown",
                )
                return LAST
        except ValueError:
            update.message.reply_text(
                "Hello Respected Sir/Madamji,\n\nWhy are you doing this? Do you find some humour? If you don't want "
                + "to schedule this greeting, then simply do /cancel and go. Please don't waste my RAM like this. Otherwise, "
                + "give me a date and time in the yyyy-mm-dd HH:MM:SS format and let me do my job. Or if you want it to "
                + "keep going on forever, reply 'never'. Praying for a quick and correct reply.\n\n"
                + "Your obedient servant,\nGoodMorningBot",
                parse_mode="markdown",
            )
            return LAST
    context.user_data[LAST] = date_object
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nThank you kindly for sending all the details. I will send your "
        + f"'{context.user_data[MESSAGE]}' greeting every {context.user_data[INTERVAL]} seconds starting "
        + (
            f"from {context.user_data[FIRST].strftime('%H:%M:%S on %d %b, %Y')} "
            if context.user_data[FIRST] is not None
            else "now "
        )
        + "until "
        + (
            f"{context.user_data[LAST].strftime('%H:%M:%S on %d %b, %Y')}."
            if context.user_data[LAST] is not None
            else "the end of time."
        )
        + "\n\n"
        + "At your service,\nGoodMorningBot",
        parse_mode="markdown",
    )
    context.job_queue.run_repeating(
        callback=get_callback(context.user_data[MESSAGE], update.effective_chat.id),
        interval=context.user_data[INTERVAL],
        first=context.user_data[FIRST],
        last=context.user_data[LAST],
        context={
            CREATOR: update.message.from_user.full_name,
            MESSAGE: context.user_data[MESSAGE],
            INTERVAL: context.user_data[INTERVAL],
            FIRST: context.user_data[FIRST]
            if context.user_data[FIRST] is not None
            else datetime.now(IST),
            LAST: context.user_data[LAST],
        },
        name=f"{update.effective_chat.id}_{time.time()}",
    )

    return ConversationHandler.END


def schedule_cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the schedule request.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation (end).
    """
    user = update.message.from_user
    logger.info(f"User {user.last_name}, {user.first_name} canceled the conversation.")
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nI am hereby canceling your request to schedul a greeting. "
        + "Hoping to be at your service sometime in the near future.\n\nYours programmatically, GoodMorningBot",
    )
    context.user_data.clear()
    return ConversationHandler.END


def get_scheduled_messages(update: Update, context: CallbackContext):
    """Get all the scheduled messages in the current chat.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation.
    """
    jobs = [
        job
        for job in job_queue.jobs()
        if job.name.startswith(str(update.effective_chat.id))
    ]
    if len(jobs) > 0:
        update.message.reply_text(
            "Hello Respected Sir/Madamji,\n\nPlease find the list of greetings that have been scheduled "
            + "in this chat below.\n\nThanks and regards,\nGoodMorningBot"
        )
        for job in jobs:
            message = f"<b>Schedule ID:</b> {job.name}\n"
            message += f"<b>Created by:</b> {job.context[CREATOR]}\n"
            message += f"<b>Greeting:</b> {job.context[MESSAGE]}\n"
            message += f"<b>Interval:</b> {job.context[INTERVAL]}\n"
            message += f"<b>Start:</b> {job.context[FIRST].strftime('%d %b, %Y at %H:%M:%S')}\n"
            message += (
                "<b>End:</b> "
                + f"{job.context[LAST].strftime('%d %b, %Y at %H:%M:%S') if job.context[LAST] is not None else 'Ad infinitum'}"
                + "\n\n"
            )
            footer = "<i>Reply to this with <code>cancel</code> in the next 15 seconds to cancel this schedule.</i>"
            sent_message = context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message + footer,
                parse_mode="HTML",
            )
            job_queue.run_repeating(
                edit_time_left,
                1,
                context={"message": sent_message, "text": message, "time_left": 14},
                name=str(sent_message.message_id),
            )
        return 1
    else:
        update.message.reply_text(
            "Hello Respected Sir/Madamji,\n\nSorry to inform you that there "
            + "are no scheduled greetings here in this chat.\n\nWith best regards,\nGoodMorningBot"
        )
        return ConversationHandler.END


def edit_time_left(context: CallbackContext):
    """Callback to edit the time left to cancel a schedule in the message generated by /list.

    Args:
        context (CallbackContext): CallbackContext for the update
    """
    message: telegram.Message = context.job.context["message"]
    text: str = context.job.context["text"]
    time_left: int = context.job.context["time_left"]
    if time_left is None:
        footer = f"<i>This schedule has been cancelled.</i>"
        message.edit_text(text + footer, parse_mode="HTML")
        context.job.schedule_removal()
        return
    if time_left == 0:
        message.edit_text(text, parse_mode="HTML")
    else:
        footer = f"<i>Reply to this with <code>cancel</code> in the next {time_left} seconds to cancel this schedule.</i>"
        message.edit_text(text + footer, parse_mode="HTML")
    time_left -= 1
    if time_left == -1:
        context.job.schedule_removal()
    else:
        context.job.context["time_left"] = time_left


def handle_schedule_cancel(update: Update, context: CallbackContext) -> int:
    """Cancel a scheduled greeting.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update

    Returns:
        int: The next state in the conversation (end).
    """
    message = update.message.reply_to_message
    job_name = re.search("^Schedule ID: ([^\s]+)\s", message.text).group(1)
    print(f"Cancelling job: {job_name}")
    job_queue.get_jobs_by_name(job_name)[0].schedule_removal()
    update.message.reply_text(
        "Hello Respected Sir/Madamji,\n\nAs requested by yourself, I have cancelled "
        + "that scheduled greeting.\n\nThanks and regards,\nGoodMorningBot"
    )
    for job in job_queue.get_jobs_by_name(str(message.message_id)):
        job.context["time_left"] = None
    return ConversationHandler.END


# ---------------------------------------------------------------------------- #
#                               Bot handler setup                              #
# ---------------------------------------------------------------------------- #

greet_command_handler = CommandHandler("greet", greet, run_async=True)
get_schedule_command_handler = ConversationHandler(
    entry_points=[CommandHandler("list", get_scheduled_messages)],
    states={},
    fallbacks=[
        MessageHandler(
            Filters.regex(re.compile(r"^cancel$", re.IGNORECASE)),
            handle_schedule_cancel,
        )
    ],
    conversation_timeout=15,
)

schedule_command_handler = ConversationHandler(
    entry_points=[CommandHandler("schedule", schedule)],
    states={
        MESSAGE: [
            MessageHandler(
                Filters.text & ~Filters.command,
                schedule_message,
            ),
        ],
        INTERVAL: [
            MessageHandler(
                Filters.regex("^[0-9]+$"),
                schedule_interval,
            )
        ],
        FIRST: [
            MessageHandler(
                Filters.regex(
                    re.compile(
                        r"^((now)|(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}))",
                        re.IGNORECASE,
                    )
                ),
                schedule_first,
            )
        ],
        LAST: [
            MessageHandler(
                Filters.regex(
                    re.compile(
                        r"^((never)|(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}))",
                        re.IGNORECASE,
                    )
                ),
                schedule_last,
            )
        ],
    },
    fallbacks=[CommandHandler("cancel", schedule_cancel)],
)

dispatcher.add_handler(greet_command_handler)
dispatcher.add_handler(get_schedule_command_handler)
dispatcher.add_handler(schedule_command_handler)

# ---------------------------------------------------------------------------- #
#                              Bot start and stop                              #
# ---------------------------------------------------------------------------- #

updater.start_polling(clean=True)

updater.idle()
