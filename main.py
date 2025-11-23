from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import ffmpeg
import pathlib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_SECRET = os.getenv("API_SECRET")

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION", "watch_tg_session")
MEDIA_CACHE = pathlib.Path("./media_cache")
MEDIA_CACHE.mkdir(exist_ok=True)

# FastAPI app
app = FastAPI()

# Telethon client
client = TelegramClient(session_name, api_id, api_hash)

# Authentication helper
def verify_token(authorization: str | None):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.split()[1]
    if token != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")


class SendMessageRequest(BaseModel):
    chat_id: int
    text: str


# STARTUP
@app.on_event("startup")
async def startup_event():
    print("Starting Telegram client...")
    await client.start()
    print("Telegram client started.")


@app.get("/status")
async def status(authorization: str = Header(None)):
    verify_token(authorization)
    return {"status": "ok"}


@app.get("/chats")
async def get_chats(authorization: str = Header(None)):
    verify_token(authorization)

    chats = []
    async for dialog in client.iter_dialogs():
        last_msg = dialog.message.message if dialog.message else ""
        chats.append({
            "id": dialog.id,
            "name": dialog.name,
            "type": dialog.entity.__class__.__name__,
            "last_message": last_msg
        })

    return {"chats": chats}


@app.get("/messages")
async def get_messages(chat_id: int, limit: int = 20,
                       authorization: str = Header(None)):
    verify_token(authorization)

    messages = await client.get_messages(chat_id, limit=limit)

    msg_list = []
    for msg in reversed(messages):
        item = {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "date": msg.date.isoformat(),
            "text": msg.message,
            "has_photo": isinstance(msg.media, MessageMediaPhoto),
            "has_document": isinstance(msg.media, MessageMediaDocument),
            "mime_type": msg.document.mime_type if msg.document else None,
        }
        msg_list.append(item)

    return {"messages": msg_list}


@app.get("/media/photo")
async def get_photo(chat_id: int, message_id: int, authorization: str = Header(None)):
    verify_token(authorization)

    msg = await client.get_messages(chat_id, ids=message_id)

    if not msg or not msg.media:
        raise HTTPException(status_code=404, detail="Media not found")

    file_path = MEDIA_CACHE / f"photo_{chat_id}_{message_id}.jpg"

    if not file_path.exists():
        await msg.download_media(file=str(file_path))

    return FileResponse(file_path, media_type="image/jpeg")


@app.get("/media/document")
async def get_document(chat_id: int, message_id: int, authorization: str = Header(None)):
    verify_token(authorization)

    msg = await client.get_messages(chat_id, ids=message_id)

    if not msg or not msg.media:
        raise HTTPException(status_code=404, detail="Media not found")

    ext = "bin"
    if msg.file:
        if msg.file.ext:
            ext = msg.file.ext.lstrip(".")
        elif msg.file.mime_type == "audio/ogg":
            ext = "ogg"
        elif msg.file.mime_type == "audio/mpeg":
            ext = "mp3"
        elif msg.file.mime_type == "video/mp4":
            ext = "mp4"

    file_path = MEDIA_CACHE / f"doc_{chat_id}_{message_id}.{ext}"

    if not file_path.exists():
        await msg.download_media(file=str(file_path))

    return FileResponse(file_path, media_type=msg.file.mime_type or "application/octet-stream")


@app.post("/send_message")
async def send_message(req: SendMessageRequest, authorization: str = Header(None)):
    verify_token(authorization)

    try:
        sent = await client.send_message(entity=req.chat_id, message=req.text)
        return {"ok": True, "message_id": sent.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_voice")
async def send_voice(
    chat_id: int,
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    verify_token(authorization)

    input_path = MEDIA_CACHE / f"upload_{chat_id}_{file.filename}"
    with open(input_path, "wb") as f:
        f.write(await file.read())

    output_path = MEDIA_CACHE / f"voice_{chat_id}.ogg"

    convert_cmd = f"ffmpeg -y -i '{input_path}' -c:a libopus -b:a 32k '{output_path}'"
    result = os.system(convert_cmd)

    if result != 0 or not output_path.exists():
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="FFmpeg conversion failed")

    try:
        sent = await client.send_file(
            entity=chat_id,
            file=str(output_path),
            voice_note=True
        )
        return {"ok": True, "message_id": sent.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


@app.get("/me")
async def me(authorization: str = Header(None)):
    verify_token(authorization)
    me = await client.get_me()
    return {"me_id": me.id}


@app.get("/media/voice")
async def get_voice(chat_id: int, message_id: int, authorization: str = Header(None)):
    verify_token(authorization)

    msg = await client.get_messages(chat_id, ids=message_id)

    if not msg or not msg.document:
        raise HTTPException(status_code=404, detail="No voice message found")

    source_path = await msg.download_media()

    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=500, detail="Failed to download voice message")

    m4a_path = source_path + ".m4a"

    (
        ffmpeg
        .input(source_path)
        .output(m4a_path, format="mp4", acodec="aac", ar=48000, ac=1, audio_bitrate="64k")
        .overwrite_output()
        .run(quiet=True)
    )

    if not os.path.exists(m4a_path):
        raise HTTPException(status_code=500, detail="Failed to create audio file")

    return FileResponse(
        m4a_path,
        media_type="audio/mp4",
        filename=f"voice_{message_id}.m4a"
    )
