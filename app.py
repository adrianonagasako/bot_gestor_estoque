from telethon import TelegramClient
from decouple import config

def connection():
    api_id = config('API_ID')
    api_hash = config('API_HASH')
    client = TelegramClient('session_name', api_id, api_hash)
    return client

async def main():
    await client.send_message('+55189880022751', 'Mensagem automática!')

if __name__ == '__main__':
    conn = connection()
    client = conn.start()
    client.loop.run_until_complete(main())