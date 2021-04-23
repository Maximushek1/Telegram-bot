import json
import logging
import signal
import sys
import time
import urllib

import requests

BOT_TOKEN = "909192061:AAE9MEVCMTDSBqxXOcEx6tsUfaIuA2Yq5XU"
OWM_KEY = "69f2a2afb10a576f876f422ad163d698"
POLLING_TIMEOUT = None


# лямбда-функции для анализа обновлений из Telegram
##используется для получения текста из сообщения в Telegram
def getText(update):
    return update["message"]["text"]


# используется для возврата местоположения из сообщения
def getLocation(update):
    return update["message"]["location"]


# используется для возврата идентификатора чата сообщения
def getChatId(update):
    return update["message"]["chat"]["id"]


# возвращает идентификатор обновления
def getUpId(update):
    return int(update["update_id"])


# возвращает результат
def getResult(updates):
    return updates["result"]


# лямбда-функции для анализа погодных условий
## возвращает описание погоды
def getDesc(w):
    return w["weather"][0]["description"]


# возвращает температуру
def getTemp(w):
    return w["main"]["temp"]


# вернет город
def getCity(w):
    return w["name"]


logger = logging.getLogger("weather-telegram")
logger.setLevel(logging.DEBUG)

# города для запросов погоды
cities = ["Moscow", "London"]


def sigHandler(signal, frame):
    logger.info("SIGINT received. Exiting... Bye bye")
    sys.exit(0)


def sigHandler(signal, frame):
    logger.info("SIGINT received. Exiting... Bye bye")
    sys.exit(0)


# настроиваем ведение журнала файлов и консоли
def configLogging():
    handler = logging.FileHandler("../run.log", mode="w")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Создаем обработчик консоли
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def parseConfig():
    global URL, URL_OWM, POLLING_TIMEOUT
    URL = "https://api.telegram.org/bot{}/".format(BOT_TOKEN)
    URL_OWM = "http://api.openweathermap.org/data/2.5/weather?appid={}&units=metric".format(OWM_KEY)
    POLLING_TIMEOUT = 5000


# делаем запрос к боту Telegram и получаем ответ в формате JSON
def makeRequest(url):
    logger.debug("URL: %s" % url)
    r = requests.get(url)
    resp = json.loads(r.content.decode("utf8"))
    return resp


# возвращаем все обновления с идентификатором
def getUpdates(offset=None):
    url = URL + "getUpdates?timeout=%s" % POLLING_TIMEOUT
    logger.info("Getting updates")
    if offset:
        url += "&offset={}".format(offset)
    js = makeRequest(url)
    return js


# создаем одноразовую клавиатуру для опций в мессенджере
def buildKeyboard(items):
    keyboard = [[{"text": item}] for item in items]
    replyKeyboard = {"keyboard": keyboard, "one_time_keyboard": True}
    logger.debug(replyKeyboard)
    return json.dumps(replyKeyboard)


def buildCitiesKeyboard():
    keyboard = [[{"text": c}] for c in cities]
    keyboard.append([{"text": "Share location", "request_location": True}])
    replyKeyboard = {"keyboard": keyboard, "one_time_keyboard": True}
    logger.debug(replyKeyboard)
    return json.dumps(replyKeyboard)


# запрашиваем в OWM погоду для места или координат
def getWeather(place):
    if isinstance(place, dict):  # coordinates provided
        lat, lon = place["latitude"], place["longitude"]
        url = URL_OWM + "&lat=%f&lon=%f&cnt=1" % (lat, lon)
        logger.info("Requesting weather: " + url)
        js = makeRequest(url)
        logger.debug(js)
        return u"%s \N{DEGREE SIGN}C, %s in %s" % (getTemp(js), getDesc(js), getCity(js))
    else:  # place name provided
        # make req
        url = URL_OWM + "&q={}".format(place)
        logger.info("Requesting weather: " + url)
        js = makeRequest(url)
        logger.debug(js)
        return u"%s \N{DEGREE SIGN}C, %s in %s" % (getTemp(js), getDesc(js), getCity(js))


# отправляем сообщение в кодировке URL на идентификатор чата
def sendMessage(text, chatId, interface=None):
    text = text.encode('utf-8', 'strict')
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(text, chatId)
    if interface:
        url += "&reply_markup={}".format(interface)
    requests.get(url)


# получаем ID последнего доступного обновления
def getLastUpdateId(updates):
    ids = []
    for update in getResult(updates):
        ids.append(getUpId(update))
    return max(ids)


chats = {}


# повторяем все сообщения
def handleUpdates(updates):
    for update in getResult(updates):
        if 'message' in update:
            chat_id = getChatId(update)
            try:
                text = getText(update)
            except Exception as e:
                logger.error("No text field in update. Try to get location")
                loc = getLocation(update)
                # была ли ранее запрошена погода?
                if (chat_id in chats) and (chats[chat_id] == "weatherReq"):
                    logger.info("Weather requested for %s in chat id %d" % (str(loc), chat_id))
                    # отправляем погоду в чат id и очистить состояние
                    sendMessage(getWeather(loc), chat_id)
                    del chats[chat_id]
                continue
            #распознавание команд и ответы для них
            if text == "/weather":
                keyboard = buildCitiesKeyboard()
                chats[chat_id] = "weatherReq"
                sendMessage("Select a city", chat_id, keyboard)
            elif text == "/start":
                sendMessage("Cahn's Axiom: When all else fails, read the instructions", chat_id)
            elif text == "/help":
                sendMessage("I can send you a weather forecast at the moment, in a certain city or in your area",
                            chat_id)
            elif text.startswith("/"):
                logger.warning("Invalid command %s" % text)
                continue
            elif (text in cities) and (chat_id in chats) and (chats[chat_id] == "weatherReq"):
                logger.info("Weather requested for %s" % text)
                # отправляем погоду на идентификатор чата и очистить состояние
                sendMessage(getWeather(text), chat_id)
                del chats[chat_id]
            else:
                keyboard = buildKeyboard(["/weather"])
                sendMessage("I learn new things every day but for now you can ask me about the weather.", chat_id,
                            keyboard)


def main():
    # настроиваем файловые и консольные регистраторы
    configLogging()
    # получаем токены и ключи
    parseConfig()

    signal.signal(signal.SIGINT, sigHandler)
    # основной цикл
    last_update_id = None
    while True:
        updates = getUpdates(last_update_id)
        if len(getResult(updates)) > 0:
            last_update_id = getLastUpdateId(updates) + 1
            handleUpdates(updates)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
