# shadowdaemon/run_all_bots.py

import re
import sys
import threading

from shadowsprite.platforms.telegram_bot import main as run_telegram
from shadowsprite.platforms.discord_bot import main as run_discord

def main():
    # 1) Start Discord in its own thread
    discord_thread = threading.Thread(
        target=run_discord,
        name="DiscordBotThread",
        daemon=True
    )
    discord_thread.start()

    # 2) Normalize argv for telegram_bot
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])

    # 3) Block on Telegram
    return run_telegram()

if __name__ == "__main__":
    sys.exit(main())
