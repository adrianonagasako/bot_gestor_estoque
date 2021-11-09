from telethon import TelegramClient, events
from decouple import config

api_id = config('API_ID')
api_hash = config('API_HASH')
client = TelegramClient('session_name', api_id, api_hash)
@client.on(events.NewMessage)

async def my_event_handler(event):
    if 'oi' in event.raw_text:
        await event.reply('teste!')
    chat = await event.get_chat()
    chat_id = event.chat_id
    sender_id = event.sender_id
    print(f'ChatID: {chat_id} SenderID: {sender_id}')
    print(type(chat))

client.start()
client.run_until_disconnected()