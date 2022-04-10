import datetime
import logging
from logging.config import dictConfig
import os
import time


from dotenv import load_dotenv
import requests
from telegram import Bot
from telegram.error import BadRequest, TimedOut, Unauthorized

from exceptions import APIError, EnvError
from log_config import log_config

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

NO_CHANGE_MESSAGE = 'Обновлений не обнаружено'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    '''Функция отсылает сообщение с помощью телеграм-бота в определённый чат.
    '''
    bot.send_message(TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    '''Функция запрашивает API данные и возвращает их тиризированными
    в Python.'''
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    r = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if not r.status_code == 200:
        raise APIError(f'не удалось получить сведения от {ENDPOINT}, '
                       f'код ответа API: {r.status_code}'
                       )
    return r.json()


def check_response(response):
    '''Функция проверяет:
    - есть ли обновление;
    - содержится ли словарь в response;
    - содержится ли в словаре по индексу homeworks список;
    - имеются ли в словаре индекс current_date и является значение
    целочисленным;
    функция возвращает список домашних работ.'''
    if not isinstance(response['current_date'], int):
        raise TypeError('Метка времени не является целочисленной')
    if not isinstance(response, dict):
        raise TypeError(f'в ответ пришёл не словарь - {response}')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'список работ - вовсе не список - {homeworks}')
    return homeworks


def parse_status(homework):
    '''Функция извлекает из входящих данных название домашней работы, её статус
    и возвращает текстовую строку для последующей отсылки телеграм ботом.'''
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Получен незадокументированный статус работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    '''Функция проверяет доступность переменных окружения, если нет
    хотя бы одной переменной, то возращает False, иначе - True.'''
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        return False


def main():
    """Делает запрос к API, проверяет ответы, при наличии обновления —
    получает статус работы из обновления и отправляет сообщение в Telegram,
    повторяет действия спустя RETRY_TIME, логирует работу
    (настройки логирования) в log_config.py.
    """
    dictConfig(log_config)
    logger = logging.getLogger(__name__)
    logger.debug('Начало работы')
    if not check_tokens():
        logger.critical('Ошибка переменных окружения')
        raise EnvError('Ошибка переменных окружения')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors_cache = -1

    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.debug('Соединение успешно')
            homeworks = check_response(response)
            chek_time = datetime.datetime.fromtimestamp(current_timestamp)
            logger.debug('Метка времени: '
                         f'{chek_time.strftime("%Y-%m-%d %H:%M:%S")}'
                         )
            # Проверка наличия метки времени происходит в main через try:,
            # поскольку pytest неадекватно реагирует на эту проверку в функции
            # check_response
            current_timestamp = response['current_date']
            if len(homeworks) == 0:
                message = NO_CHANGE_MESSAGE
            else:
                message = parse_status(homeworks[0])
            logger.debug(message)

        except Exception as error:
            # Чтобы отправлять сообщения из одного места и не отправлять
            # ошибки, связанные с чтением API повторно, вводится кэш ошибок,
            # который обнуляется каждый раз, когда возникает ошибка
            # не связанная с получением и чтением API
            if isinstance(error, (APIError, KeyError, TypeError)):
                errors_cache += 1
                logger.debug('Количество повторных ошибок, '
                             f'не отосланных в телеграм: {errors_cache}'
                             )
            else:
                errors_cache = -1
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

        finally:
            if not(message == NO_CHANGE_MESSAGE) and not (errors_cache > 0):
                try:
                    send_message(bot=bot, message=message)
                    logger.info('Сообщение успешно отправлено в телеграм')
                except Unauthorized as error:
                    logger.error('Ошибка отправки телеграм-сообщения: '
                                 f'бот {error}'
                                 )
                except BadRequest as error:
                    logger.error('Ошибка отправки '
                                 f'телеграм-сообщения: {error}'
                                 )
                except TimedOut as error:
                    logger.error('Ошибка отправки '
                                 f'телеграм-сообщения: {error}'
                                 )
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
