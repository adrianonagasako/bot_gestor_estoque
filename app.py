import os
import time
import asyncio
from decouple import config
from telethon import TelegramClient, events, Button
from telethon.tl import types
from lib.database import DB

api_id = config('API_ID')
api_hash = config('API_HASH')
bot_token = config('BOT_TOKEN')
bot = TelegramClient('bot', api_id, api_hash).start(bot_token)
con = DB()
chat_id = -739573656
download_path = '\workspaces\\bot_gestor_estoque\\media\\'
phone_user = None
request = [] 

def cancel_op():
    global phone_user
    phone_user = None
    
def to_float(value):
    return float(value.strip("R$").replace('.','').replace(',','.'))

def to_real(value):
    x = '{:,.2f}'.format(float(value))
    return x.replace(',','#').replace('.',',').replace('#','.')

def to_date(value):
    x = str(value)
    return f'{x[4:6]}/{x[2:4]}/20{x[0:2]} as {x[6:8]}:{x[8:10]}'
#========================================================= captador de novas mensagens ========================================================================

@bot.on(events.NewMessage)
async def handler(event):                                                               #função que inicia a interação do bot
    
    async def get_phone(sender_id):                                                     #função que pede o número de celular caso o bot não receber do telegram
        cel = ('message', 'Por favor digite seu número celular telegram (Com DDD e somente números)')
        phone = await chat_bot(sender_id, cel)
        while type(phone) != list: 
            if not phone:
                return
            elif not phone.isnumeric():
                phone = await chat_bot(sender_id, ('message', 'Digite apenas números\nDigite novamente:'))
            elif len(phone) != 11:
                phone = await chat_bot(sender_id, ('message', 'Você digitou uma quantidade incompatível de dígitos, tente novamente:'))
            else:
                confirm_cel = ('button', f'O número {phone} está correto?', ('SIM', 'EDITAR'))
                callback = await chat_bot(sender_id, confirm_cel)
                if not callback:
                    return
                elif callback == b'SIM':
                    phone = [phone]
                elif callback == b'EDITAR':
                    cel = ('message', 'Por favor digite seu número celular (Com DDD e somente números)')
                    phone = await chat_bot(sender_id, cel)
        return phone[0]
    
    global phone_user
    sender = await event.get_sender()
    if event.raw_text == 'oi' or event.raw_text == 'Oi':
        if not phone_user:                                                              #começa a validação e se já tiver validado, segue para próxima fase
            if event.chat_id == chat_id:                                                #Valida o grupo de vendas
                query = f"SELECT aproved, phone, name_rs FROM usuario WHERE iduser = {sender.id}"
                result = con.consult(query)
                if event.chat.admin_rights.ban_users == True:                           #valida se o usuário é administrador
                    phone_user = 'admin'
                    await menu_admin(event)
                else:            
                    try:                                                                #tenta fazer uma consulta, caso for excessão, ele irá para o menu de registro
                        if result[0][0] == None:                                        #verifica se o usuário já foi registrado ou aguardando aprovação
                            await event.reply('Acabei de verificar que seu cadastro está em aprovação, em breve receberá confirmação de sua aprovação, obrigado e até breve!')
                        elif result[0][0] == True:
                            phone_user = result[0][1]
                            await bot.send_message(event.sender_id, f'Seja bem vindo, {result[0][2]}')
                            await user_menu(event)                                      #inicia o menu de compras do usuário
                    except IndexError:
                        if not sender.phone:
                            phone = await get_phone(sender.id)
                            if not phone:
                                return
                            else:
                                phone_user = phone
                        else:
                            phone_user = sender.phone
                        await register_user(event)                                      #chama a função de registro de usuário                     
    elif event.raw_text == '/pedidos':
        if event.chat_id == chat_id:                                                    #Valida o grupo de vendas
            query = f"SELECT aproved, phone, name_rs FROM usuario WHERE iduser = {sender.id}"
            result = con.consult(query)
            try:
                phone_user = result[0][1]
                await bot.send_message(event.sender_id, f'Seja bem vindo, {result[0][2]}')
                await view_requests(event)
            except IndexError:
                pass
#================================================== funções que criam conversas interativas ===================================================================   

def press_event(user_id):
    return events.CallbackQuery(func=lambda e: e.sender_id == user_id)                  #retorna o evento de clique
    
def respond_event(user_id):
    return events.NewMessage(func=lambda e: e.sender_id == user_id)                     #retorna o evento de resposta

async def chat_bot(user_id, quest):                                                     #função que recebe mensagens e botões, espera o retorno e devolve para função que a chama
    answer = None
    try:
        async with bot.conversation(user_id) as conv:                                       #inicia uma conversa
            if quest[0] == 'button':                                                        #recebe o primeiro ítem da tupla onde fica armazenado o tipo de interação
                button = []
                for item in quest[2]:                                                       #recebe e insere os botões na pergunta
                    button.append(Button.inline(item))
                choose = await conv.send_message(quest[1], buttons=button)
                answer_obj = await conv.wait_event(press_event(user_id), timeout=120)
                answer = answer_obj.data
                await bot.delete_messages(user_id, conv._get_message_id(choose))            #apaga os botões da conversa para não permitir executar uma ação fora de sua sessão
            elif quest[0] == 'message':
                await conv.send_message(quest[1])
                response = await conv.wait_event(respond_event(user_id), timeout=120)
                answer = response.message.text
            elif quest[0] == 'img':
                await conv.send_message(quest[1])
                response = await conv.wait_event(respond_event(user_id), timeout=120)
                try:
                    attributes = response.message.media.document.attributes
                    for attr in attributes:
                        if isinstance(attr, types.DocumentAttributeFilename):
                            file_path = os.path.join(download_path+quest[2], attr.file_name)
                    if response.message.media is not None:
                        message = await response.message.reply('baixando...')
                        await bot.download_media(response.message, file_path)
                        await message.edit('Baixado com sucesso')
                        answer = file_path
                except Exception:
                    answer = response.message.text
            return answer
    except asyncio.TimeoutError:
        await bot.send_message(user_id, 'Sessão expirada, recomece novamente com um oi no grupo de vendas')

#===================================================  funções de usuário administrador  ======================================================================== 

async def menu_admin(event):                                                            #função de menu inicial do usuário administrador
    async def view_request(idrequest):                                                  #função de visualização dos pedidos, mensagens e arquivos
        query = f"SELECT status FROM request WHERE id = {idrequest}"
        status = con.consult(query)
        img = []
        i = 0 
        total = 0
        query = f"SELECT name, prod_units, price_unit FROM prod_request INNER JOIN products ON prod_request.idproducts = products.idproducts WHERE idrequest = {idrequest} ORDER BY id ASC"
        products = con.consult(query)   
        query = f"SELECT who_sent, message FROM chat WHERE idrequest = {idrequest} ORDER BY id ASC"
        messages = con.consult(query)
        det_request = f'Pedido: {idrequest}\nData da compra: {to_date(idrequest)}\nStatus: {status[0][0]}\n \n'
        for prod in products:
            total += prod[1] * prod[2]
            det_request += f'{prod[1]}X {prod[0]}\n'
            det_request += f'Valor unitário: {prod[2]}\n \n'
        det_request += f'\nValor total:   R${to_real(total)}\n \n'
        det_request += 'MENSAGENS ===================\n \n'
        if len(messages) > 0:
            for msg in messages:
                if msg[1][0:11] == '\workspaces':
                    img.append(msg[1])
                    i += 1
                    file_name = msg[1].rsplit('\\')
                    det_request += f'Enviado por: {msg[0]} em {to_date(idrequest)}:\n/BAIXAR_{i} {file_name[-1]}\n \n'
                else:
                    det_request += f'Mensagem enviada por {msg[0]} em {to_date(idrequest)}\n{msg[1]}\n \n'
        else:
            det_request += f'O comprador fez o pedido, mas não enviou mensagens!!!\n \n'
        det_request += 'Clique em /CONTINUAR para o próximo passo.'
        callback = await chat_bot(event.sender_id, ('message', det_request))
        if not callback:
            await bot.send_message(event.sender_id, f'Você não interagiu com o pedido nº {idrequest}')
        elif callback[0:7] == '/BAIXAR':
            j = int(callback.strip("/BAIXAR_"))-1
            await bot.send_message(event.sender_id, 'Baixando arquivo, se for imagem, ele irá abrir como foto', file = img[j])
            await view_request(idrequest)
            
    async def change_status(idrequest):                                                 #função de alteração de status de pedido
        async def set_new_status(new_status):                                           #função que define o status escolhido
            query = f"SELECT iduser, status FROM request WHERE id = {idrequest}"
            id_user = con.consult(query)
            if id_user[0][1] == 'Cancelado':
                await bot.send_message(event.sender_id, f'NÃO É POSSÍVEL ALTERAR STATUS DE PEDIDOS "CANCELADOS"\nO status do pedido nº {idrequest} não foi alterado')
            else:
                set_status = f"UPDATE request SET status = '{new_status}' WHERE id = {idrequest}"
                con.manipulate(set_status)
                if new_status == 'Entregue':
                    goodbye = f'Parabéns, o vendedor alterou o status do pedido {idrequest}, para {new_status}.'
                    goodbye += 'Pedimos para que envie opiniões e avaliação dos produtos no grupo de vendas e caso tenha algum problema com a compra,'
                    goodbye += 'você pode acessar o seu pedido digitando /pedidos no grupo de vendas e nos enviando uma mensagem '
                    goodbye += 'que faremos o pós-venda por lá! Obrigado pela sua compra e até a próxima!!'
                    await bot.send_message(id_user[0][0], goodbye)
                elif new_status == 'Cancelado':
                    query = f"SELECT idproducts, prod_units FROM prod_request  WHERE idrequest = {idrequest}"
                    prod = con.consult(query)
                    give_back = f"UPDATE products SET units = (SELECT units FROM products WHERE idproducts = {prod[0][0]})+{prod[0][1]} WHERE idproducts = {prod[0][0]}"
                    con.manipulate(give_back)
                    goodbye = f'O vendedor alterou o status do pedido {idrequest}, para {new_status}.'
                    goodbye += 'Você pode acessar seu pedido digitando /pedidos no grupo de vendas, '
                    goodbye += 'e nos enviando uma mensagem que responderemos assim que possível. '
                    await bot.send_message(id_user[0][0], goodbye)
                else:
                    await bot.send_message(id_user[0][0], f'O vendedor alterou o status do pedido {idrequest}, para {new_status}')
        choose = '/STATUS_1 "Aguardando endereço e forma de pagamento"\n'
        choose += '/STATUS_2 "Aguardando pagamento"\n'
        choose += '/STATUS_3 "Produto enviado"\n'
        choose += '/STATUS_4 "Entregue"\n'
        choose += '/STATUS_5 "Cancelado"\n'
        choose += '/STATUS_6 "Desistência ou defeito"'
        callback = await chat_bot(event.sender_id, ('message', choose))
        if not callback:
            await bot.send_message(event.sender_id, f'O status do pedido nº {idrequest} ficou pendente de sua escolha')
        if callback == '/STATUS_1':
            await set_new_status("Aguardando endereço e forma de pagamento")
        if callback == '/STATUS_2':
            await set_new_status("Aguardando pagamento")
        if callback == '/STATUS_3':
            await set_new_status("Produto enviado")
        if callback == '/STATUS_4':
            await set_new_status("Entregue")
        if callback == '/STATUS_5':
            await set_new_status("Cancelado")
        if callback == '/STATUS_6':
            await set_new_status("Desistência ou defeito")
        await list_request(idrequest)
    
    async def new_message(idrequest):                                                   #função de visualização de mensagens e respostas
        async def rec_message(new_message):
            new_mess_id = time.strftime("%y%m%d%H%M%S", time.localtime())
            insert_message = f"INSERT INTO chat (id, idrequest, who_sent, message) VALUES ({new_mess_id}, {idrequest}, 'vendedor', '{new_message}')"
            con.manipulate(insert_message)
            query = f"SELECT iduser FROM request WHERE id = {idrequest}"
            id_user = con.consult(query)
            await bot.send_message(id_user[0][0], f'O vendedor lhe enviou nova mensagem no pedido {idrequest}, digite /pedidos no grupo de vendas e confira a mensagem no pedido correspondente')
            callback = await chat_bot(event.sender_id, ('button', 'Você deseja alterar o status do pedido?', ('SIM', 'NÃO')))
            if not callback:
                await bot.send_message(event.sender_id, f'Você não decidiu se irá alterar o status do pedido nº {idrequest}')
            elif callback == b'SIM':
                await change_status(idrequest)
        temp_message = 'Digite uma mensagem para o comprador ou\n'
        temp_message += 'Clique em /ENVIAR para enviar um arquivo / imagem\n'
        temp_message += 'Clique em /SAIR para sair sem enviar nada.'
        callback = await chat_bot(event.sender_id, ('message', temp_message))
        if not callback:
            await bot.send_message(event.sender_id, f'Você não interagiu com o pedido nº {idrequest}')
        elif callback == '/SAIR':
            pass
        elif callback == '/ENVIAR':
            send_img = ['img', 'escolha um arquivo por mensagem (imagens deverão ser enviadas como arquivo)', idrequest]
            callback = await chat_bot(event.sender_id, send_img)
            if not callback:
                await bot.send_message(event.sender_id, f'Você não enviou o arquivo no pedido nº {idrequest}')
            else:
                await rec_message(callback)
        else:                   
            await rec_message(callback)
                
    async def approve_user(users_unreg, index):                                         #função de aprovação do cadastro de usuários
        user = users_unreg[index]
        reg_message = 'O cadastro a seguir está pendente de aprovação:\n'
        reg_message += f'Nome completo ou Razão Social: {user[2]}\n'
        reg_message += f'CPF ou CNPJ: {user[3]}\n'
        reg_message += f'RG ou inscrição estadual: {user[4]}'
        callback = await chat_bot(event.sender_id, ('button', reg_message, ('ACEITAR', 'RECUSAR', 'PROXIMO')))
        if not callback:
            await bot.send_message(event.sender_id, 'Ainda há cadastros pendentes de aprovação.')
        elif callback == b'ACEITAR':
            query = f"UPDATE usuario SET aproved = TRUE WHERE iduser = {user[0]}"
            con.manipulate(query)
            await bot.send_message(event.sender_id, 'O cadastro foi aprovado')
            await bot.send_message(user[0], 'Seja bem vindo, seu cadastro foi aprovado, de um oi no grupo de vendas para ver nossas promoções!')
        elif callback == b'RECUSAR':
            refuse = ('message', 'Porque o cadastro está sendo recusado?')
            callback = await chat_bot(event.sender_id, refuse)
            query = f"DELETE FROM usuario WHERE iduser = {user[0]}"
            con.manipulate(query)
            await bot.send_message(event.sender_id, 'O usuário foi avisado e os dados foram apagados do registro')
            await bot.send_message(user[0], f'Seu cadastro foi recusado, motivo: {callback}')
        elif callback == b'PROXIMO':
            if len(users_unreg) < index:
                approve_user(users_unreg, index + 1)
            else:
                callback = await chat_bot(event.sender_id, ('button', 'Não há mais cadastros pendentes de aprovação.\n \nClique em VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('VOLTAR', 'SAIR')))
                if not callback:
                    await bot.send_message(event.sender_id, 'Você estava vendo cadastros pendentes de aprovação.')
                elif callback == b'VOLTAR':
                    await menu_admin(event)
                elif callback == b'SAIR':
                        pass
        elif callback == b'VOLTAR':
            await menu_admin(event)
        elif callback == b'SAIR':
            pass
                
    async def manage_products():                                                        #função de gerenciamento de produtos
        async def product_reg():                                                        #função de criação de cadastro de novos produtos
            async def get_img():                                                        #função de adicionar foto do produto
                async def get_more_img():                                               #função para adicionar fotos complementares
                    reg_img = ['img', 'Envie outra foto, ou clique em /PARAR se terminou', new_product_id]
                    callback = await chat_bot(event.sender_id, reg_img)
                    if callback == '/PARAR':
                        for itens in add_img:
                            imgs.append(itens)
                    elif not callback:
                        cancel_op()
                        return
                    else:
                        add_img.append(callback)
                        await get_more_img()
                        
                reg_img = ['img', 'Envie uma foto do produto, (envie como arquivo)', new_product_id]       
                callback = await chat_bot(event.sender_id, reg_img)
                if not callback:
                    cancel_op()
                    return
                else:
                    imgs.append(callback)
                add_img = []
                await get_more_img()
            
            new_product_id = time.strftime("%y%m%d%H%M", time.localtime())
            product = []
            register = (('message','Digite o nome do produto:'),
                        ('message','Digite a descrição do produto:'),
                        ('message','Digite detalhes sobre o produto:'),
                        ('message','Digite o valor unitário do produto:'),
                        ('message','Digite quantas peças tem no estoque:'))
            for quest in register:
                callback = await chat_bot(event.sender_id, quest)
                if not callback:
                    cancel_op()
                    return   
                else:
                    product.append(callback)
            imgs = []       
            await get_img()
            query = f"INSERT INTO products (idproducts, name, description, details, price, units) VALUES ({new_product_id}, '{product[0]}', '{product[1]}', '{product[2]}', {to_float(product[3])}, {product[4]})"
            con.manipulate(query)
            for image in imgs:
                query2 = f"INSERT INTO prod_img (idproducts, img_name) VALUES ({new_product_id}, '{image}')"
                con.manipulate(query2)
            descript = product[1].rsplit('.')
            if len(descript) > 1:
                descript = descript[0]+'.\n'+descript[1].strip()+'...\n'
            else:
                descript = descript[0]
            await bot.send_message(chat_id, 'ATENÇÃO ESTAMOS COM NOVO PRODUTO NO ESTOQUE!!!')
            await bot.send_message(chat_id, product[0], file = imgs[0])
            await bot.send_message(chat_id, 'Descrição:\n'+descript+'\nPara saber mais, dê um oi, encontre o produto e clique em detalhes')
            callback = await chat_bot(event.sender_id, ('button', 'Clique no botão correspondente a sua ação', ('CADASTRAR OUTRO', 'VOLTAR AO MENU')))
            if not callback:
                cancel_op
                return
            elif callback == b'VOLTAR AO MENU':
                await menu_admin(event)
            elif callback == b'CADASTRAR OUTRO':
                await product_reg()
            
        await product_reg()
    
    async def list_request(request):                                                    #função de listagem de pedidos
        if request is None:
            query = "SELECT id FROM request WHERE status != 'Cancelado' AND status != 'Entregue' ORDER BY id ASC"
            requests = con.consult(query)
            temp_message = 'Listando pedidos não cancelados ou entregues:\n \n'
            for req in requests:
                temp_message += f'/PEDIDO_{req[0]}\n'
            callback = await chat_bot(event.sender_id, ('message', temp_message))
            if not callback:
                await bot.send_message(event.sender_id, 'Você não acessou o pedido, tente mais tarde')
            elif callback[0:7] == '/PEDIDO':
                request = int(callback.strip("/PEDIDO_"))
        await view_request(request)
        #await new_message(request)
        callback = await chat_bot(event.sender_id, ('button', 'Escolha entre alterar o status do pedido, ver mensagens, voltar a lista de pedidos, voltar ao menu inicial ou encerrar a sessão\n \nVocê pode digitar o Nº do Pedido mesmo entregue ou fechado', ('ALT STATUS', 'MENSAGENS', 'LISTA', 'VOLTAR', 'SAIR')))
        if not callback:
            await bot.send_message(event.sender_id, f'Você estava acompanhando o pedido {request}')
        elif callback == b'LISTA':
            await list_request(None)
        elif callback == b'ALT STATUS':
            await  change_status(request)
            await list_request(None)
        elif callback == b'MENSAGENS':
            await new_message(request)
            await list_request(None)
        elif callback == b'VOLTAR':
            await menu_admin(event)
        elif callback == b'SAIR':
            pass
        else:
            await list_request(callback)
    
    async def no_answered_messages(no_ans_mess, index):                                 #função que enfilera as mensagens pendentes de respostas
        if index < len(no_ans_mess) :
            no_msg = no_ans_mess[index]
            await view_request(no_msg[index])
            await new_message(no_msg[index])
            check_answered = f"UPDATE chat SET answered = TRUE WHERE id = {no_msg[0]}"
            con.manipulate(check_answered)
            callback = await chat_bot(event.sender_id, ('button', 'Clique em PROXIMO para a próxima mensagem pendente, VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('PROXIMO', 'VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Ainda há compradores esperando respostas')
            elif callback == b'PROXIMO':
                await no_answered_messages(no_ans_mess, index+ 1)
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
        else:
            callback = await chat_bot(event.sender_id, ('button', 'Não há mais mensagens pendentes\n \nClique em VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Você estava respondendo as mensagens dos compradores')
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
            
    async def requests_expired(req_no_chat, index):                                     #função que enfilera os pedidos que não tiveram resposta a mais de 2 dias
        if index <= len(req_no_chat) :
            no_msg = req_no_chat[index]
            await view_request(no_msg[index])
            await new_message(no_msg[index])
            callback = await chat_bot(event.sender_id, ('button', 'Clique em PROXIMO para a próxima mensagem pendente, VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('PROXIMO', 'VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Ainda há pedidos sem resposta')
            elif callback == b'PROXIMO':
                await no_answered_messages(req_no_chat, index+ 1)
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
        else:
            callback = await chat_bot(event.sender_id, ('button', 'Não há mais mensagens pendentes.\n \nClique em VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Você estava vendo pedidos sem resposta')
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
        
    async def messages_expired(chat_expired, index):                                    #função que enfilera os pedidos com interação do vendedor onde o comprador não se manifestou a mais de 3 dias
        if index <= len(chat_expired) :
            no_msg = chat_expired[index]
            await view_request(no_msg[index])
            await new_message(no_msg[index])
            callback = await chat_bot(event.sender_id, ('button', 'Clique em PROXIMO para a próxima mensagem pendente, VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('PROXIMO', 'VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Ainda há pedidos sem respostas a mais de 3 dias')
            elif callback == b'PROXIMO':
                await no_answered_messages(chat_expired, index+ 1)
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
        else:
            callback = await chat_bot(event.sender_id, ('button', 'Não há mais mensagens pendentes\n \nClique em VOLTAR para ir para o menu inicial ou SAIR para encerrar a Sessão', ('VOLTAR', 'SAIR')))
            if not callback:
                await bot.send_message(event.sender_id, 'Você estava vendo os pedidos abandonados')
            elif callback == b'VOLTAR':
                await menu_admin(event)
            elif callback == b'SAIR':
                pass
                                                #-----------     menu de boas vindas     -----------
                                                
    query = f"SELECT * FROM usuario WHERE aproved IS NOT TRUE"
    approve_users = con.consult(query)
    query = f"SELECT id, idrequest FROM chat WHERE answered = FALSE ORDER BY id ASC"
    no_answ_mess = con.consult(query)
    tda_request = time.strftime("%y%m%d%H%M", time.localtime(time.time() + (3600 * 24 * -2)))
    query = f"SELECT request.id FROM request LEFT JOIN chat ON  request.id = chat.idrequest WHERE chat.id IS NULL AND request.id < {tda_request} AND request.status != 'Cancelado'"
    req_no_chat = con.consult(query)
    tda_chat = time.strftime("%y%m%d%H%M%S", time.localtime(time.time() + (3600 * 24 * -3)))
    query = f"SELECT idrequest FROM chat JOIN request ON  request.id = chat.idrequest WHERE chat.who_sent = 'vendedor' AND request.status != 'Entregue' AND request.status != 'Cancelado' AND chat.id < {tda_chat}"
    chat_expired = con.consult(query)
    wellcome_message = 'Seja bem vindo vendedor\n \n'
    if len(approve_users) > 0:
        wellcome_message += f'\n{len(approve_users)} /CADASTROS aguardando aprovação.\n'
    elif len(req_no_chat) > 0:
        wellcome_message += f'{len(req_no_chat)} /PEDIDOS aguardando contato a mais de 2 dias.\n'
    elif len(no_answ_mess) > 0:
        wellcome_message += f'{len(no_answ_mess)} /_MENSAGENS te aguardando.\n' 
    elif len(chat_expired) > 0:
        wellcome_message += f'{len(chat_expired)} /MENSAGENS suas sem resposta a mais de 3 dias.\n'
    wellcome_message += '/LISTAR_PRODUTOS (gerenciar produtos).\n/LiSTAR_PEDIDOS não finalizados.\n/SAIR'   
    callback = await chat_bot(event.sender_id, ('message', wellcome_message))
    if not callback:
        await bot.send_message(event.sender_id, 'A seleção de tarefas do menu inicial expirou')
    elif callback == '/CADASTROS':
        await approve_user(approve_users, 0)
    elif callback == '/PEDIDOS':
        await requests_expired(req_no_chat, 0)
    elif callback == '/_MENSAGENS':
        await no_answered_messages(no_answ_mess, 0)
    elif callback == '/MENSAGENS':
        await messages_expired(chat_expired, 0)
    elif callback == '/LiSTAR_PEDIDOS':
        await list_request(None)
    elif callback == '/LISTAR_PRODUTOS':
        await manage_products()
    await bot.send_message(event.sender_id, 'Sessão Finalizada')
    cancel_op()
    
#===================================================== funções de Cadastro de usuário ==========================================================================
async def register_user(event):                                                         #função de cadastro de usuários
    async def start_register():                                                         #função inicial de cadastro
        answers = []
        register = (('message','Digite seu nome completo ou razão social'),
                    ('message','Digite seu CPF ou CNPJ'),
                    ('message','Digite o RG ou inscrição estadual'))
        for quest in register:
            callback = await chat_bot(event.sender_id, quest)
            if not callback:
                cancel_op()
                return  
            else:
                answers.append(callback)
        aprove_data = (('button',f'Verifique se os dados estão corretos:\nNome completo ou razão social: {answers[0]}\n'+
                    f'CPF ou CNPJ: {answers[1]}\nRG ou inscrição estadual: {answers[2]}', ('PROSSEGUIR', 'EDITAR DADOS', 'CANCELAR CADASTRO')))
        callback = await chat_bot(event.sender_id, aprove_data)
        if not callback:
            cancel_op() 
        elif callback == b'PROSSEGUIR':
            query = f"INSERT INTO usuario (iduser, phone, name_rs, cpf_cnpj, rg_insc) VALUES ({event.sender_id}, {phone_user}, '{answers[0]}', '{answers[1]}', '{answers[2]}')"
            con.manipulate(query)
            await bot.send_message(event.sender_id, 'Você receberá uma mensagem assim que seu cadastro for aprovado, muito obrigado e até logo!')
            cancel_op()
        elif callback == b'CANCELAR CADASTRO':
            await bot.send_message(event.sender_id, 'Cadastro cancelado, quando quiser se cadastrar, basta enviar um oi no grupo de vendas, obrigado e até a próxima!')
            cancel_op()
        elif callback == b'EDITAR DADOS':
            await start_register()

    accept_register = ('button','Eu identifiquei que você não está cadastrado e para continuar, terá que nos fornecer dados cadastrais e aguardar aprovação. Você concorda com isso?', ('SIM', 'NÃO'))
    callback = await chat_bot(event.sender_id, accept_register)                         #aceite dos termos que o usuário terá que enviar os dados cadastrais para prosseguir
    if not callback:
        cancel_op()
        return 
    if callback == b'SIM':
        await start_register()
    else:
        cancel_op()
    
 #=================================================================== Menu de Usuário Aprovado ==================================================================================
    
async def user_menu(event):                                                             #função inicial ou menu de usuário
    
    async def create_request(id_product, name_product, units, price_product):           #função de criação do pedido do usuário
        
        async def list_request():                                                       #função que lista os produtos, quantidade e valores no pedido
            total = 0
            if len(request) > 0:
                i=0
                products_list = 'Clique em /FINALIZAR para encerrar e pagar a compra ou\nClique em /CONTINUAR_COMPRANDO para voltar ou\nClique em /CANCELAR para cancelar o pedido ou\nClique no marcador correspondente para remover algum item do carrinho:\n \n'
                for product in request:
                    i += 1
                    total += product[3]
                    products_list += f'/REMOVER_{i}: {product[2]} X {product[1]}\n'
                if i == 0:
                    await user_menu(event)
                else:    
                    callback = await chat_bot(event.sender_id, ('message', f'{products_list}\n \n Valor total do pedido: R${to_real(total)}'))
                    if not callback:
                        request.clear()
                        cancel_op()
                        return
                    elif callback == '/FINALIZAR':
                        await send_request(event)
                    elif callback == '/CONTINUAR_COMPRANDO':
                        await user_menu(event)
                    elif callback == '/CANCELAR':
                        await bot.send_message(event.sender_id, 'O pedido foi cancelado!')
                        request.clear()
                        cancel_op()
                        return
                    else:
                        listed = int(callback.strip("/REMOVER_"))-1
                        new_request = []
                        j=0
                        for item in request:
                            if j != listed:    
                                new_request.append(item)
                            j+=1    
                        request.clear()
                        if len(new_request) > 0:
                            for item in new_request:
                                request.append(item)
                        await list_request()
            else:
                await bot.send_message(event.sender_id, 'O pedido está vazio!')
                await user_menu(event)            
        if not id_product is None:
            request.append([id_product, name_product, units, price_product])
        await list_request()           
    async def list_products(result): #--------------------------------------------------#Função Listar Produtos
        async def view_product(prod_name): #--------------------------------------------#Função Visualizar Produto
            async def add_product(): #--------------------------------------------------#Função de adicionar produto ao pedido
                async def value_stock(units):                                           #Função de adicionar quantidade de produtos ao pedido
                    while type(units) != list: 
                        if not units:
                            return
                        elif not units.isnumeric():
                            units = await chat_bot(event.sender_id, ('message', 'A quantidade precisa ser um número ex.: 1\nDigite a quantidade:'))
                        elif int(units) > product_results[0][5]:
                            units = await chat_bot(event.sender_id, ('message', 'Você digitou um número maior que a quantidade disponível, por favor digite um número menor!'))
                        else:
                            units = [units]
                    return int(units[0])
   
                prod_qt = ('message', f'Existem {product_results[0][5]} unidades disponíveis a venda, quantas unidades você deseja incluir ao pedido?')
                callback = await chat_bot(event.sender_id, prod_qt)
                units = await value_stock(callback)
                if not units:
                    cancel_op()
                    return
                confirmate = ('button', f'{units} X {product_results[0][1]}\n \nValor total: R${to_real(product_results[0][4] * units)}', ('ADICIONAR AO PEDIDO', 'DESISTIR'))
                callback = await chat_bot(event.sender_id, confirmate)                
                if not callback:
                    cancel_op()
                    return
                elif callback == b'DESISTIR':
                    await view_product(prod_name)
                elif callback == b'ADICIONAR AO PEDIDO':
                    await create_request(product_results[0][0], product_results[0][1], units, product_results[0][4] * units)


            async def view_details(): #--------------------------------------------------Função Ver Detalhes
                desc = await bot.send_message(event.sender_id, f'Descrição completa:\n{product_results[0][2]}')
                async with bot.conversation(event.sender_id) as conv:
                    choose = await conv.send_message(f'Detalhes:\n{product_results[0][3]}', buttons=Button.inline('VOLTAR'))
                    await conv.wait_event(press_event(event.sender_id), timeout=600)
                    await bot.delete_messages(event.sender_id, conv._get_message_id(choose))
                await bot.delete_messages(event.sender_id, desc)
                prod = [product_results[0]]
                prod.append(images)
                await view_product(prod)
            if type(prod_name) != list:
                query = f"SELECT idproducts, name, description, details, price, units FROM products WHERE name LIKE '{prod_name}%'"
                product_results = con.consult(query)
                query_imgs = f"SELECT img_name FROM prod_img WHERE idproducts = {product_results[0][0]}"
                img = con.consult(query_imgs)
                images = []
                for image in img:
                    images.append(image[0])
                await bot.send_message(event.sender_id, product_results[0][1], file = images)
            else:
                images = prod_name[-1]
                prod_name.pop()
                product_results = prod_name
            desc = product_results[0][2].rsplit('.')        
            if len(desc) > 1:
                descript = f'Valor Unitário: R${to_real(product_results[0][4])}\n \n{desc[0]}.\n{desc[1].strip()}...\n'
            else:
                descript = f'Valor Unitário: R${to_real(product_results[0][4])}\n \n{desc[0]}...\n'
            descript += '\nClique em DETALHES para mais informações\nClique em COMPRAR fazer o pedido'
            descript += '\nClique em VOLTAR para voltar ao primeiro menu ou SAIR para encerrar o atendimento'
            description = ('button', descript, ('DETALHES', 'COMPRAR', 'VOLTAR', 'SAIR'))
            callback = await chat_bot(event.sender_id, description)
            if not callback:
                cancel_op()
                return
            elif callback == b'DETALHES':
                await view_details()
            elif callback == b'COMPRAR':
                await add_product()
            elif callback == b'VOLTAR':
                await user_menu(event)
            elif callback == b'SAIR':
                await bot.send_message(event.sender_id, 'Atendimento Encerrado, até logo!')
                cancel_op()
                return
   
        i=0
        products_list = 'Clique no marcador correspondente ao nome do produto para ver o anúncio:\n'
        for products in result:
            i += 1
            prod = products[0].rsplit(',')
            products_list += f'/PRODUTO_{i}: {prod[0]}\n'
        if i == 0:
            await user_menu(event)
        else:    
            callback = await chat_bot(event.sender_id, ('message', products_list))
            if not callback:
                cancel_op()
                return
            else:
                listed = int(callback.strip("/PRODUTO_"))-1
                await view_product(result[listed][0])
    
        

    wellcome = ('message', 'Você pode digitar o que está procurando ou\nClicar em /LISTA para ver uma lista de nossos produtos ou\nClicar em /VER_PEDIDO para ver o pedido caso tenha ítens comprados')
    callback = await chat_bot(event.sender_id, wellcome)
    if not callback:
        cancel_op()
    elif callback == '/LISTA':
        query = "SELECT name FROM products WHERE units > 0"
        result = con.consult(query)
        if not result:
            callback = await chat_bot(event.sender_id, ('button', 'No momento não há produtos disponíveis a venda, volte mais tarde', ('VOLTAR',)))
            if not callback:
                cancel_op()
            else:
                await user_menu(event)
        else:
            await list_products(result)
    elif callback == '/VER_PEDIDO':
        if len(request) > 0:
            await create_request(None, None, None, None)
        else:
            await bot.send_message(event.sender_id, 'Lista de pedidos vazia')
            await user_menu(event)
    else:
        query = f"SELECT name FROM products WHERE name LIKE '%{callback}%' AND units > 0 ORDER BY name ASC"
        result = con.consult(query)
        if not result:
            await bot.send_message(event.sender_id, f'Não encontrei produtos com "{callback}" no nome')
            await user_menu(event)
        else:
            await bot.send_message(event.sender_id, f'Eu encontrei {len(result[0])}produto(s) correspondente(s) a "{callback}":')
            await list_products(result)

#========================================================  Controle de pedidos =================================================================================
async def send_request(event):                                                          #função de confirmação de pedido, onde o registro vai para o banco de dados
    new_request_id = time.strftime("%y%m%d%H%M", time.localtime())
    insert_request = f"INSERT INTO request (id, iduser, status) VALUES ({new_request_id}, {event.sender_id}, 'Aguardando endereço e forma de pagamento')"
    con.manipulate(insert_request)
    for product in request:
        insert_prod_request = f"INSERT INTO prod_request (idrequest, idproducts, price_unit, prod_units) VALUES ({new_request_id}, {product[0]}, {product[3]}, {product[2]})"
        con.manipulate(insert_prod_request)
        reserve_product_unit = f"UPDATE products SET units = (SELECT units FROM products WHERE idproducts = {product[0]}) - {product[2]} WHERE idproducts = {product[0]}"
        con.manipulate(reserve_product_unit)
    payment_message = f'O número do seu pedido é {new_request_id}\n \nPara acessá-lo digite /pedidos no grupo de vendas\n \n'
    payment_message += 'Acesse agora e acompanhe o status do pedido, envie os dados do seu endereço para cálculo de frete e se prefere '
    payment_message += 'pagar por transferência bancária, pix, código de barras ou cartões através do link de pagamento via PagSeguro ou Mercado Pago'
    await bot.send_message(event.sender_id, payment_message)

async def view_requests(event):                                                         #função de visualização de pedidos anteriores
    async def view_prod_req():                                                          #função de visualização de produtos, quantidade e valores dos pedidos
        async def list_msg():                                                           #função de listagem de mensagens para os pedidos
            async def rec_message(message):                                             #função de gravação de novas mensagens
                new_mess_id = time.strftime("%y%m%d%H%M%S", time.localtime())
                insert_message = f"INSERT INTO chat (id, idrequest, who_sent, message, answered) VALUES ({new_mess_id}, {the_request}, 'você', '{message}', FALSE)"
                con.manipulate(insert_message)
                await bot.send_message(event.sender_id, 'O vendedor foi notificado, você receberá uma resposta em breve!')
                await list_msg()
            img = []
            i = 0    
            query = f"SELECT id, who_sent, message FROM chat WHERE idrequest = {the_request} ORDER BY id ASC"
            messages = con.consult(query)
            if messages == []:
                 temp_message = 'Ainda não há mensagens enviadas ou recebidas.\n \n'
            else:
                temp_message = 'Para baixar os arquivos, clique em BAIXAR\n \n'
                temp_message += 'Mensagens anteriores:\n \n'
                for mess in messages:
                    if mess[2][0:11] == '\workspaces':
                        img.append(mess[2])
                        i += 1
                        file_name = mess[2].rsplit('\\')
                        temp_message += f'Enviado por: {mess[1]} em {to_date(mess[0])}:\n/BAIXAR_{i} {file_name[-1]}\n \n'
                    else:
                        temp_message += f'Mensagem enviada por {mess[1]} em {to_date(mess[0])}\n{mess[2]}\n \n'    
            temp_message += 'Lembrete: Já deixou os dados de entrega e a preferência do método de pagamento?\n'
            temp_message += 'Agora você já pode digitar a mensagem!\n'
            temp_message += 'Clique em /VOLTAR para retornar aos pedidos\n'
            temp_message += 'Clique em /SAIR para encerrar o atendimento\n'
            temp_message += 'Clique em /ENVIAR para enviar um arquivo / imagem\n'
            callback = await chat_bot(event.sender_id, ('message', temp_message))
            if not callback:
                cancel_op()
            elif callback[0:7] == '/BAIXAR':
                j = int(callback.strip("/BAIXAR_"))-1
                await bot.send_message(event.sender_id, 'Baixando arquivo, se for imagem, ele irá abrir como foto', file = img[j])
                await list_msg()
            elif callback == '/VOLTAR':
                await view_requests(event)
            elif callback == '/SAIR':
                await bot.send_message(event.sender_id, 'Obrigado pela preferência e até breve!!!')
                cancel_op()
            elif callback == '/ENVIAR':
                send_img = ['img', 'escolha um arquivo por mensagem (imagens deverão ser enviadas como arquivo)', the_request]
                callback = await chat_bot(event.sender_id, send_img)
                if not callback:
                    cancel_op()
                else:
                    await rec_message(callback)
            else:                   
                await rec_message(callback)
        
        total = 0
        det_request = f'Pedido {the_request}\nStatus: {req[1]}\n\n'
        query = f"SELECT products.idproducts, name, prod_units, price_unit, units FROM prod_request INNER JOIN products ON prod_request.idproducts = products.idproducts WHERE idrequest = {the_request} ORDER BY id ASC"
        products = con.consult(query)
        for prod in products:
            total += prod[2] * prod[3]
            det_request += f'{prod[2]}X {prod[1]}\n'
        det_request += f'\nValor total:   R${to_real(total)}\n \nClique em SAIR para finalizar o atendimento\nClique em VOLTAR para escolher outro pedido\n'
        det_request += 'Clique em MENSAGENS para ver o histórico e enviar novas mensagens'
        
        callback = await chat_bot(event.sender_id, ('button', det_request,('SAIR', 'VOLTAR', 'MENSAGENS')))
        if not callback:
            cancel_op()
        elif callback == b'VOLTAR':
            await view_requests(event)
        elif callback == b'SAIR':
            await bot.send_message(event.sender_id, 'Obrigado pela preferência e até breve!!!')
            cancel_op()
        elif callback == b'MENSAGENS':
            await list_msg()

    query = f"SELECT id, status FROM request WHERE iduser = {event.sender_id} ORDER BY id ASC"
    requests = con.consult(query)
    if len(requests) < 1:
        await bot.send_message(event.sender_id, 'Desculpe, eu não encontrei pedidos no seu histórico!')
        cancel_op()
    else:
        list_requests = 'Clique no pedido para ver detalhes e mandar mensagem para o vendedor:\n \n'
        for req in requests:
            list_requests += f'/PEDIDO_{req[0]}\nStatus: {req[1]}\n'
        callback = await chat_bot(event.sender_id, ('message', list_requests))
        if not callback:
            cancel_op()
        else:
            the_request = callback.strip("/PEDIDO_")
            await view_prod_req()
   
    
bot.start(bot_token)
bot.run_until_disconnected()