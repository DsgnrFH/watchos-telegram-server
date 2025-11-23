# WatchOS Telegram Backend

A lightweight FastAPI + Telethon backend used by the [watchOS Telegram client](https://github.com/DsgnrFH/watchos-telegram-client).

## Setup

1. Install dependencies:
   - `pip install -r requirements.txt`
   - `sudo apt install ffmpeg`

2. Create a `.env` file in the project root:

   API_SECRET=your_api_token  
   TG_API_ID=your_telegram_api_id  
   TG_API_HASH=your_telegram_api_hash  
   TG_SESSION=watch_tg_session  

   - Get TG_API_ID and TG_API_HASH from: https://my.telegram.org

3. Run the server:

   uvicorn main:app --host 0.0.0.0 --port 8000

## Auth

All requests must include this header:

Authorization: Bearer API_SECRET

## Endpoints (short)

- GET /status — health check  
- GET /chats — list chats  
- GET /messages — list messages in a chat  
- GET /media/photo — fetch photo  
- GET /media/document — fetch generic media (video, files, etc.)  
- GET /media/voice — fetch voice note (converted to M4A)  
- POST /send_message — send text message  
- POST /send_voice — upload & send voice note
