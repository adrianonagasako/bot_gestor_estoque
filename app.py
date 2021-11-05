from telethon import TelegramClient, events
from decouple import config

# These example values won't work. You must get your own api_id and
# api_hash from https://my.telegram.org, under API Development.

def connection():
    api_id = config('API_ID')
    api_hash = config('API_HASH')

    client = TelegramClient('session_name', api_id, api_hash)
    return client


def main():
    while True:
        @client.on(events.NewMessage())
        async def handler(event):
            chat = await event.get_chat()
            sender = await event.get_sender
            with open('F:\workspaces\bot_gestor_estoque\log.txt', 'w') as l:
                l.write(f"Chat: {chat}\n Sender: {sender}\n")
            print(f'Chat: {chat}')
            print(f'Sender: {sender}')
            await event.reply('Hey!')

#print(client.get_me().stringify())
#
#client.send_message('username', 'Hello! Talking to you from Telethon')
#client.send_file('username', '/home/myself/Pictures/holidays.jpg')
#
#client.download_profile_photo('me')
#messages = client.get_messages('username')
#messages[0].download_media()


if __name__ == '__main__':
    conn = connection()
    client = conn.start()
    client.run_until_disconnected(main())