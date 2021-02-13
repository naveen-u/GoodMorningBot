# GoodMorningBot

Be the annoying Indian uncle you were always meant to be, with **GoodMorningBot**. Generate badly edited greeting messages on the fly.

## Development

#### Pre-requisites:

- python3
- A telegram bot token: https://core.telegram.org/bots#6-botfather

#### Steps:

To set up a development instance, do the following:

1. Clone this repository.

```bash
git clone https://github.com/naveen-u/GoodMorningBot.git
```

2. Create a virtual environment and install dependencies.

```bash
virtualenv venv
pip3 install -r requirements.txt
```

3. Create a `.env` file and save your telegram bot token. Your token should be something along the lines of `110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw` (this is a dummy token, as given [here](https://core.telegram.org/bots#6-botfather). Replace this with your token in the command below).

```bash
echo "TELEGRAM_BOT_TOKEN=110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" > .env
```

## Development Instance Deployment

Run `python3 bot.py` from the root directory.

## Authors

- **Naveen Unnikrishnan** - _Initial work_ - [naveen-u](https://github.com/naveen-u)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
