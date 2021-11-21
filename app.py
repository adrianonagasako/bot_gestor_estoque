from types import coroutine
from telethon.sync import TelegramClient, events
from decouple import config
from lib.database import DB

#lista contendo 2 listas, a primeira grava os eventos por passagem e a segunda grava o processo
#processo 0 = sem cadastro
pass_events = [[], []]
fst_name = []

api_id = config('API_ID')
api_hash = config('API_HASH')
client = TelegramClient('session_name', api_id, api_hash)    
@client.on(events.NewMessage)

async def handler(event):
    chat = await event.get_chat()
    sender = await event.get_sender()
    if pass_events[1] == 0:
        await cadastro(event)
    else:
        if chat.id == 538148718:
            #verifica se o usuário é admin do grupo, e encaminhado a árvore adequada
            if chat.admin_rights == True or chat.creator == True:
                await is_admin(event)
            else:
                await not_admin(event, sender.first_name)
        else:
            await not_admin(event)           


async def cadastro(event):
        pass_events[0].append(event)
        if len(pass_events[0]) == 3:
            if event.message.message == '3':
                pass_events[0].clear()
                pass_events[1] = None
                await client.send_message(event.chat_id, 'Encerrar')
                await client.send_message(event.chat_id, 'Obrigado por sua visita e até breve!')
            elif event.message.message == '2':
                pass_events[0].pop()
                pass_events[0].pop()
                pass_events[1] = None
                await client.send_message(event.chat_id, 'Voltar')
                await client.send_message(event.chat_id, 'responda com 1 para comprar ou 2 para vender')
            elif event.message.message == '1':
                print('iniciando cadastro')
            else:
                pass_events[0].pop()
                await client.send_message(event.chat_id, 'Não identifiquei sua resposta, responda 1 para se cadastrar, responda 2 para voltar ao menu anterior e responda 3 para encerrar')
            #event.from_id.user_id
        
        
#Árvore do chat de controle administrativo  
async def is_admin(event):
    pass_events[0].append(event)


#Árvore do chat de iteração de nível usuário
async def not_admin(event, name):
    #gravando a instância atual do evento na lista pass_events
    pass_events[0].append(event)
    fst_name.append(name)
    #perguntas por nível
    resp1_a = 'responda com 1 para comprar ou 2 para vender'
    
    #Mensagem de boas vindas
    if len(pass_events[0]) == 1:
        await client.send_message(event.chat_id, f'Olá {fst_name[0]}, ' + resp1_a)
        
    #Retorno da primeira iteração
    if len(pass_events[0]) == 2:
        if event.message.message == '1':
            await client.send_message(event.chat_id, 'comprar')
        elif event.message.message == '2':
            await client.send_message(event.chat_id, 'vender')
            query = f'SELECT EXISTS (SELECT iduser FROM usuario WHERE iduser = {event.from_id.user_id})::int'
            con = DB()
            result = con.consult(query)
            if result[0][0]<1:
                await client.send_message(event.chat_id, 'Eu identifiquei que você não está cadastrado e para continuar, terá que nos fornecer os dados cadastrais e aguardar aprovação da nossa administração você concorda com isso? Caso sim, responda 1, responda 2 para retornar ao menu anterior ou responda com 3 para encerrar')
                pass_events[1] = 0
        else:
            await client.send_message(event.chat_id, 'Não identifiquei sua resposta, ' + resp1_a)
            pass_events.pop()
           
    
    if len(pass_events[0]) == 3:
        print('3 passagens')
    if len(pass_events[0]) == 4:
        print('4 passagens')
                
client.start()
client.run_until_disconnected()   