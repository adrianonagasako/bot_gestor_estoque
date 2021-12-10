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

#=========================================================== captador de novas mensagens ========================================================================

@bot.on(events.NewMessage(pattern='oi'))
async def handler(event):
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
    if not phone_user:                                                                  #começa a validação e se já tiver validado, segue para próxima fase
        if event.chat_id == chat_id:                                                    #Valida o grupo de vendas
            query = f"SELECT aproved, phone, name_rs FROM usuario WHERE iduser = {sender.id}"
            result = con.consult(query)
            if not event.chat.admin_rights.ban_users == True:                               #valida se o usuário é administrador
                phone_user = 'admin'
                await menu_admin(event)
            else:            
                try:                                                                    #tenta fazer uma consulta, caso for excessão, ele irá para o menu de registro
                    if result[0][0] == None:                                            #verifica se o usuário já foi registrado ou aguardando aprovação
                        await event.reply('Acabei de verificar que seu cadastro está em aprovação, em breve receberá confirmação de sua aprovação, obrigado e até breve!')
                    elif result[0][0] == True:
                        phone_user = result[0][1]
                        await bot.send_message(event.sender_id, f'Seja bem vindo, {result[0][2]}')
                        await user_menu(event)                                          #inicia o menu de compras do usuário
                except Exception:
                    if not sender.phone:
                        phone = await get_phone(sender.id)
                        if not phone:
                            return
                        else:
                            phone_user = phone
                    else:
                        phone_user = sender.phone
                    await register_user(event)                                          #chama a função de registro de usuário                     

#===================================================== funções que criam conversas interativas ===========================================================================   

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

#=========================================================  funções de usuário administrador  ================================================================================ 

async def menu_admin(event):                                                            #função de menu inicial do usuário administrador
    async def approve_user(user):                                                       #função de aprovação do cadastro de usuários
        reg_message = ('button', 'O cadastro a seguir está pendente de aprovação:\n'+
                    f'Nome completo ou Razão Social: {user[2]}\n'+
                    f'CPF ou CNPJ: {user[3]}\n'+
                    f'RG ou inscrição estadual: {user[4]}', ('ACEITAR', 'RECUSAR'))
        callback = await chat_bot(event.sender_id, reg_message)
        if not callback:
            cancel_op()
            return
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
            
    async def manage_products():
        async def product_reg():
            async def get_img():
                async def get_more_img():
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
            
           
                                                #-----------     menu de boas vindas     -----------
            
    wellcome_message = ('button', 'Seja bem vindo administrador, escolha a opção que deseja: ', ('APROVAR USUÁRIOS', 'GERENCIAR PRODUTO(S)', 'SAIR'))
    callback = await chat_bot(event.sender_id, wellcome_message)
    if not callback:
        cancel_op()
        return  
    elif callback == b'APROVAR USU\xc3\x81RIOS':                                          #escolha de aprovação de cadastro
        query = f"SELECT * FROM usuario WHERE aproved IS NOT TRUE"
        result = con.consult(query)
        #try:
        for users_unreg in result:
            await approve_user(users_unreg)
        await bot.send_message(event.sender_id, 'Não há mais cadastros pendentes de aprovação')
        await menu_admin(event)
        #except Exception:
            #await bot.send_message(event.sender_id, 'Não há usuários pré-cadastrados')
    elif callback == b'GERENCIAR PRODUTO(S)':                                          #escolha para cadastro de produtos
        await manage_products()
    elif callback == b'SAIR':
        await bot.send_message(event.sender_id, 'Sessão Finalizada')
        cancel_op()
#============================================================ funções de Cadastro de usuário =================================================================================
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
    
async def user_menu(event):
    async def create_request(id_product, name_product, units, price_product):
        async def list_request():
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
                        await bot.send_message(event.sender_id, 'O pedido foi enviado para o vendedor!')
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
    async def list_products(result): #----------------------------------------------------------------------------------------Função Listar Produtos
        async def view_product(prod_name): #-------------------------------------------------------------------------------Função Visualizar Produto
            async def add_product(): #---------------------------------------------------------------------------------------Função de adicionar produto ao pedido
                async def value_stock(units):
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
                    
            

            async def view_details(): #-------------------------------------------------------------------------------------------Função Ver Detalhes
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
            elif callback == b'DETALHES':   #--------------------------------------------------------------------------------------Detalhes
                await view_details()
            elif callback == b'COMPRAR':    #--------------------------------------------------------------------------------------Comprar
                await add_product()
            elif callback == b'VOLTAR':    #---------------------------------------------------------------------------------------Voltar
                await user_menu(event)
            elif callback == b'SAIR':    #-----------------------------------------------------------------------------------------Sair
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
    
    
    

bot.start(bot_token)
bot.run_until_disconnected()