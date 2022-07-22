from urllib.request import urlopen

import bs4
import urllib3
from bs4 import Tag

siteURL = 'https://ilibrary.ru'
searchURL = 'https://ilibrary.ru/search.phtml?q='

def handler(event, context):
    """
    Entry-point for Serverless Function.
    :param event: request payload.
    :param context: information about current execution context.
    :return: response to be serialized as JSON.
    """

    pIndex = event.get('state', {}).get('session', {}).get('pIndex')
    reader_state = event.get('state', {}).get('session', {}).get('reader_state')
    href = event.get('state', {}).get('session', {}).get('href')
    intents = event.get('request', {}).get('nlu', {}).get('intents', {})
    command = event.get('request', {}).get('command')
    isNew = event.get('session', {}).get('new')

    namePiece = None
    save = event.get('state', {}).get('user', {})

    if isinstance(save.get('namePiece'), str):
        namePiece = save.get('namePiece')

    if isNew and not namePiece is None:
        pIndex = max(0, save.get('pIndex')-1)
        href = save.get('href')
        reader_state = 'save_loading'

    end_session = 'false'

    if not isinstance(reader_state, str):
        reader_state = 'searching'

    if reader_state == 'searching':
        if len(command) == 0:
            text = 'Привет! Что вы бы хотели прослушать?'
        else:
            cmd = command.encode('cp1251').hex()
            url = searchURL + getByteURL(cmd)
            searchPage = getPageByURL(url)

            #BY AUTHOR
            if isAuthorPage(searchPage):
                text = getAuthorDialogue(searchPage)
            else:
                href = getFirstPageURL(searchPage)
                text = getQuestionForRead(searchPage)
                namePiece = getPieceName(searchPage)
                reader_state = 'reading'
                pIndex = 0
    elif reader_state == 'reading':
        if 'готов' in command or 'да' in command or 'дальше' in command:
            bookPage = getPageByURL(siteURL + href)
            nextPage = getNextPage(bookPage)
            resultText = "Произведение прочитано. Что бы вы хотели прослушать еще?"
            p = getParagraph(bookPage.find_all('span', {"class": "p"}))
            
            if nextPage == "":
                if pIndex == len(p):
                    resultText = "Произведение прочитано. Что бы вы хотели прослушать еще?"
                    reader_state = "searching"
                else:
                    resultText = p[pIndex]
                    pIndex += 1
            else:
                if pIndex == len(p):
                    pIndex = 0
                    href = nextPage
                    bookPage = getPageByURL(siteURL + href)
                    p = getParagraph(bookPage.find_all('span', {"class": "p"}))
                resultText = p[pIndex]
                pIndex += 1
                        
            text = resultText
        elif 'нет' in command or 'остановись' in command:
            text = 'Хорошо. Что бы вы хотели прослушать еще?'
            reader_state = 'searching'
    elif reader_state == 'save_loading':
        if len(command) == 0:
            text = 'В прошлый раз вы остановились на произведении ' + namePiece
            text += '. Желаете продолжить?'
        elif 'нет' in command:
            text = 'Хорошо. Что бы вы хотели прослушать?'
            namePiece = None
            reader_state = 'searching'
        elif 'да' in command:
            text = 'Хорошо. Скажите, как будете готовы'
            reader_state = 'reading'

    response = {
        'version': event['version'],
        'session': event['session'],
        'response': {
            'text': text,
            'end_session': end_session
        },
        'user_state_update': {
            'pIndex': pIndex, 
            'href': href,
            'namePiece': namePiece
        },
        'session_state': {
            'pIndex': pIndex, 
            'href': href, 
            'namePiece': namePiece,
            'reader_state': reader_state,
        }
    }
    return response

def getNextPage(text):
    a = text.find('div', {"id": "text"}).find('a', {"title": "Дальше"})
    if not (a is None):
        return a.get('href')
    return ""
    
def getParagraph(lst):
    result = []
    for t in lst:
        broken = break1024(t.get_text())
        for b in broken:
            result.append(b)
    result = union1024(result)
    return result


def union1024(lst):
    splitter = 1024
    result = []
    once = lst[0]
    lst.remove(once)

    for l in lst:
        if len(once) + len(l) + 1 <= splitter:
            once += ' ' + l
        else:
            result.append(once)
            once = l
    if len(once) != 0:
        result.append(once)
    return result


def break1024(lst):
    splitter = 1024
    result = []
    index = 0
    while index < len(lst):
        result.append(lst[index:splitter + index])
        index += splitter
    return result

def getFirstPageURL(text):
    page = text.find('div', {"id": "text"}).find('ul').find('li').find('a')
    return page['href']

def getPieceName(text):
    return text.find('div', {"id": "text"}).find('ul').find('li').get_text()

def getQuestionForRead(text):
    question = "Вы хотите прослушать " + getPieceName(text) + "?"
    return question

def getPageByURL(url):
    html_doc = urlopen(url).read()
    return bs4.BeautifulSoup(html_doc, 'html.parser')
   
def getAuthorDialogue(text):
    firstAuthor = next(iter(text.find('ul').find('li')), None)
    authorPage = getPageByURL(siteURL + firstAuthor['href'])
    firstPiece = authorPage.find('span', {"id": "text"}).find('p').text
    dialogue = 'По вашему запросу найден лишь автор. Постарайтесь указать на его произведение. ' \
               'Например: ' + firstAuthor.text + ", " + firstPiece
    return dialogue

def isAuthorPage(text) :
    div = text.find('div', {"id": "text"})
    h3 = div.find('h3')
    if not isinstance(h3, Tag):
        return False
    return 'Авторы' in h3.text

def getByteURL(url):
    result = '%' + url
    i = 3
    while i < len(result):
        result = result[:i] + '%' + result[i:]
        i += 3
    return result
