from http.server import BaseHTTPRequestHandler,HTTPServer
from os import path, mkdir
import datetime
import time
import json

try:
    import requests
    import socks
    from urllib.parse import unquote
except ImportError:
    log('Установите модули requests, socks, urllib')
    exit()

global key
key = 'af0deccbgcgidddjgnvljitntccdduijhdinfgjgfjir' #ключ для доступа к api авито

def unblockSession():
    pass
def url_to_json(url):
    #декодируем url-encoded строку в обычную и возвращаем пробелы
    url = unquote(url).replace('+', ' ')
    #делим строку на отдельные теги по символу &
    tags = url.split('&')
    #записываем пары ключ:значение, разделив теги по знаку =
    json = dict([tags[i].split('=') for i in range(len(tags))])
    return(json)

def log(text):
    #пишем лог, состоящий из времени записи и содержания как в консоль, так и в файл log.txt рядом со скриптом
    log_str = '[{time}] {text}\n'.format(time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S'), text = text)
    print(log_str)
    with open('log.txt', 'a', encoding = 'utf-8') as file:
        file.write(log_str)

def writePages(jsonResponse, filename):
    #переписываем файл с результатами с добавлением новой страницы
    with open(filename, 'w', encoding = 'utf-8') as file:
        file.write(str(jsonResponse))

def getIDs(response):
    """
    Метод получения ID объявлений со страницы поисковой выдачи

    На каждой странице объявления идут подряд и ID можно
    получить из json напрямую по пути items -> value -> id,
    но иногда могут встречаться списками из нескольких
    объявлений вместе, где структура items -> value -> list -> массив из value -> id
    """
    IDs = []
    try:
        items = response['result']['items']
        for item in items:
            try:
                IDs.append(item['value']['id'])
            except KeyError:
                listID = item['value']['list']
                for ID in listID:
                    IDs.append(ID['value']['id'])
        return IDs
    except KeyError:
        log(response)

def getResult(IDs, session):
    """
    Метод получения данных из ID объявлений на странице

    Для каждого ID из полученного списка пытаемся получить
    страницу с объявлением, в случае неудачи
    пишем в логи ответ авито
    """
    result = []
    for ID in IDs:
        response = getIDPage(ID, key, session)
        
        try:
            resultID = {
                'title': response['title'],
                'desc': response['description'],
                'url': response['sharing']['url'],
                'price': response['price']['value'],
                #получаем дату и время публикации на основе timestamp, которая хранится у каждого объявления
                'pubDate': datetime.datetime.fromtimestamp(response['time']).strftime('%d-%m-%Y %H:%M:%S')
            }
            
            result.append(resultID)
            log('ID {} parsed'.format(ID))
            #time.sleep(0.1)
        except KeyError:
            log(response)

    return result 

def getPage(query, key, pageNumber, session):
    """
    Метод получения страницы ответа по номеру страницы и запросу

    Отправляем GET запрос api авито и ждем ответа в течении 10 секунд,
    в случае тайм-аута отправляем бессрочный запрос, чтобы
    точно получить ответ

    Иногда авито может забанить сессию, поэтому сразу же проверяем
    полученную страницу на наличие в ней объявлений
    """
    log('Start page {}'.format(pageNumber))
    try:
        response = session.get('https://m.avito.ru/api/9/items',
                               params={'query': query,'key': key, 'page': pageNumber}, timeout = 10.0).json()
    except requests.exceptions.Timeout:
        log('Page {} time out'.format(pageNumber))
        response = session.get('https://m.avito.ru/api/9/items',
                               params={'query': query,'key': key, 'page': pageNumber}).json()
    try:
        items = response['result']['items']
        return response
    except KeyError:
        log('Bad page:\n{}'.format(str(response)))

def getIDPage(ID, key, session):
    """
    Метод получения объявления по ID

    Отправляем GET запрос api авито и ждем ответа в течении 10 секунд,
    в случае тайм-аута отправляем бессрочный запрос, чтобы
    точно получить ответ
    """
    try:
        response = session.get('https://m.avito.ru/api/15/items/{}'.format(ID),
                                params={'key': key}, timeout = 10.0).json()
    except requests.exceptions.Timeout:
        log('Page timed out (ID {})'.format(ID))
        response = session.get('https://m.avito.ru/api/15/items/{}'.format(ID),
                                params={'key': key}).json()
    return response

def initSession(proxies):
    #авито позволяет работать с api только при наличии валидного кука ft (взял из своего браузера)
    cookie = 'ft = "aWVqnfFwPg3eMJX5V155X3wvYCmLNG6lIgT1TsDqWGNXbTq73kVX+4CMh2+zk3Ws3Ui3OGNXgCByFomiPUOE323drU/oiZVmG91L5/x+54IWe/E8aKUC+rDLjQfptd/X8Q2iuabprpEUp4MQQbrD8+7vRp3gKYAKvLY7YXjLavQOYTFBgIOX2t7WpYGWEHhF"'
    #в заголовки добавим user-agent реального браузера и куки ft
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.135 YaBrowser/21.6.2.854 Yowser/2.5 Safari/537.36', 'cookie': cookie}
    session = requests.Session()
    #используем прокси, если они есть
    if (proxies):
        session.proxies.update(proxies)
    session.headers.update(headers)
    return session

class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        #отвечаем на GET запрос сообщением, что ждем POST
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        self.wfile.write(b'Recieved GET request (POST expected)')

    def do_POST(self):
        """
        Обработка POST-запроса

        Скрипт читает данные, которые были переданы вместе с POST-запросом,
        из входного файла сервера и конвертирует их в json-формат для
        упрощения дальнейшей работы

        В данном методе вызывается метод parse() в случае получения
        корректных данных в POST-запросе или отправляется ответ,
        в котором сообщается о невозможности обработки запроса
        """
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        data_string = self.rfile.read(int(self.headers['Content-Length']))
        json_rcvd = url_to_json(data_string)

        try:
            #получаем поисковый запрос из данных POST-запроса
            query = json_rcvd['search']
            
            try:
                #пытаемся получить адрес прокси, если не получается - оставляем прокси пустыми
                proxy = json_rcvd['proxies']
                proxies = {'http': 'socks5://{}'.format(proxy), 'https': 'socks5://{}'.format(proxy)}
            except KeyError:
                proxies = ''

            try:
                #пытаемся получить адрес callback, если не получается - оставляем пустым
                callback = json_rcvd['callback']
            except KeyError:
                callback = ''

            HttpHandler.parse(self, query, callback, proxies)

        except KeyError:
            self.wfile.write(b'Received uncorrect data')
            log('Recieved uncorrect data:\n{}'.format(json_rcvd))

    def sendResponse(self, jsonResponse, callback, session):
        #при наличии адреса callback, отправляем на него страницу с результатом поиска
        if (callback):
            session.post(callback, data = jsonResponse)
            log('Callback done')
        #если адреса нет - пишем ответ отправителю POST запроса
        else:
            self.wfile.write(bytes(jsonResponse, 'utf-8'))
            self.wfile.write(b'\n\n')

    def parse(self, query, callback, proxies):
        """
        Основной метод парсинга

        Получает на вход поисковый запрос, адрес callback и прокси
        Результаты парсинга записываются в папку results, логи сохраняются
        в файл log.txt рядом со скриптом

        Скрипт запрашивает у api авито страницу поисковой выдачи,
        получает из нее ID объявлений, заходит на каждое
        и собирает нужную информацию 
        """
        
        #создаем папку results, если ее не было
        if not path.exists('results'):
            mkdir('results')
            
        #файл с результатами называем согласно поисковому запросу и времени его получения
        timestamp = datetime.datetime.now().strftime('%d_%m_%Y__%H_%M_%S')
        filename = 'results\search_{query}__{timestamp}.txt'.format(query = query, timestamp = timestamp)
        #создаем новую сессию с прокси (если они были переданы)
        session = initSession(proxies)
        response = getPage(query, key, 1, session)
        pageNumber = 1
        #лимит выдачи авито - 100 страниц
        pageLimit = 100
        result = getResult(getIDs(response), session)
        mainResult = result
        jsonResponse = {'search': query, 'result': result}
        HttpHandler.sendResponse(self, json.dumps(jsonResponse), callback, session)
        writePages(jsonResponse, filename)
        log('Page 1 done')
        time.sleep(1)

        try:
            count = response['result']['count']

            #идем по страницам, пока не дошли до лимита и на страницах есть объявления
            while (pageNumber < pageLimit and count > 0):
                pageNumber += 1
                response = getPage(query, key, pageNumber, session)
                result = getResult(getIDs(response), session)
                mainResult += result
                jsonResponse = {'search': query, 'result': result}
                #http-ответ отправляем постранично
                HttpHandler.sendResponse(self, json.dumps(jsonResponse), callback, session)
                jsonResponse = {'search': query, 'result': mainResult}
                #в файл записываем все страницы вместе для сохранения результата
                writePages(jsonResponse, filename)
                count = response['result']['count']
                log('Page {} done'.format(pageNumber))
                time.sleep(1)
        except KeyError:
            #записываем в лог ответ авито в случае, если не удалось получить count со страницы
            log(response)

        #закрываем сессию после парсинга
        session.close()

#запускаем сервер
server = HTTPServer(('localhost', 8000), HttpHandler)
server.serve_forever()
