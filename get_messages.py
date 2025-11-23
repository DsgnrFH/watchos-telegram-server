import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION", "watch_tg_session")

async def main():
    chat_id = int(input("Enter chat ID: "))

    # Fetch last 20 messages
    messages = await client.get_messages(chat_id, limit=20)

    for msg in reversed(messages):
        sender = msg.sender_id
        text = msg.message or "[media]"
        print(f"{msg.id} | sender {sender}: {text}")

if __name__ == "__main__":
    client = TelegramClient(session_name, api_id, api_hash)

    async def runner():
        async with client:
            await main()

    asyncio.run(runner())
