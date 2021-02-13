import json
import logging
import os
import random
import re
import textwrap
from io import BytesIO
from typing import List, NamedTuple, Tuple

import dotenv
import requests
from PIL import Image, ImageDraw, ImageFont
from telegram.ext import CommandHandler, Updater
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update

# ---------------------------------------------------------------------------- #
#                                 Configuration                                #
# ---------------------------------------------------------------------------- #

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

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

# ---------------------------------------------------------------------------- #
#                                 Greet command                                #
# ---------------------------------------------------------------------------- #

updater = Updater(token=TELEGRAM_TOKEN)
dispatcher = updater.dispatcher


def greet(update: Update, context: CallbackContext):
    """Create a WhatsApp family group-style forward image
    with a quote and the given greeting.

    Args:
        update (Update): Update from telegram
        context (CallbackContext): CallbackContext for the update
    """
    quote = get_random_quote()
    message = ""
    if context.args is not None:
        message = " ".join(context.args)
    if message.strip() == "":
        message = "Good Morning!"
    image = make_greeting(quote.strip(), message.strip())
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=image)


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
    ):
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
#                               Bot handler setup                              #
# ---------------------------------------------------------------------------- #

greet_command_handler = CommandHandler("greet", greet, run_async=True)
dispatcher.add_handler(greet_command_handler)

# ---------------------------------------------------------------------------- #
#                              Bot start and stop                              #
# ---------------------------------------------------------------------------- #

updater.start_polling(clean=True)

updater.idle()
