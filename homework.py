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
# По требованиям pytest в файле должны быть эти переменные
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

# Настройки логера и его объявление вынесены за пределы main() в связи с
# требованием логировать то, что происходит внутри функций. В частности
# добавить в логи информацию о том, какой именно токен недоступен в функции
# check_tokens() или ввести страховочный код в send_message().
# Во избежание странностей и для удобства настройки имя логера задано жёстко.
dictConfig(log_config)
logger = logging.getLogger('homework')


def send_message(bot, message):
    """Функция отсылает сообщение с помощью телеграм-бота...
    в определённый чат.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
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
    except Exception as error:
        logger.error('Ошибка отправки '
                     f'телеграм-сообщения: {error}'
                     )


def get_api_answer(current_timestamp):
    """Функция запрашивает API данные и возвращает их тиризированными...
    в Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    request_details = (
        f'  URL: {ENDPOINT}\n'
        f'  Параметры запроса: {params}\n'
    )
    try:
        # Ситуация дисконекта и невозможности преобразования в json закрыта
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response_json = response.json()
    except Exception as error:
        logger.error(f'Ошибка соединения: {error}' + request_details)
    else:
        logger.debug('Соединение успешно')
    # В дальнейшем response всегда будет доступен.
    # Все детали сетевого запроса, а именно: URL и параметры
    # Можно использовать response.__dict__, но вероятно нет смысла.
    request_details = (
        'ошибка АPI.\n' + request_details
        + f'  код ответа: {response.status_code}\n'
        f'  Ответ: {response_json}'
    )
    if not response:
        raise APIError(request_details)
    # Поиск ключей 'error' или 'code'
    if ('error' in response_json):
        raise requests.JSONDecodeError(request_details)
    if ('code' in response_json):
        raise requests.JSONDecodeError(request_details)
    return response_json


def check_response(response):
    """Функция проверяет:...
    - есть ли обновление;
    - содержится ли словарь в response;
    - содержится ли в словаре по индексу homeworks список;
    - имеются ли в словаре индекс current_date и является значение
    целочисленным;
    функция возвращает список домашних работ.
    """
    if not isinstance(response['current_date'], int):
        raise TypeError('Метка времени не является целочисленной')
    if not isinstance(response, dict):
        raise TypeError(f'в ответ пришёл не словарь - {response}')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'список работ - вовсе не список - {homeworks}')
    return homeworks


def parse_status(homework):
    """Функция извлекает из входящих данных название домашней работы, её статус...
    и возвращает текстовую строку для последующей отсылки телеграм ботом.
    """
    if not isinstance(homework, dict):
        raise TypeError('Информация о домашнем задании - не слловарь: '
                        f'{homework}'
                        )
    homework_name = homework.get('homework_name')
    # При получении значения из словаря через get функция не должна упасть
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Получен незадокументированный статус работы: '
                       f'{homework_status}'
                       )
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверяет доступность переменных окружения, если нет...
    хотя бы одной переменной, то возращает False, иначе - True; логирует
    на уровне critical каких именно переменных не хватает.
    """
    # Правильно было бы вынести это в начало файла, и свести все токены
    # в словарь, а затем брать значения из словаря, но pytest требуют
    # наличия переменных в которых будут токены.
    TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    # Можно перенести логирование в main(), но в ревью вопрос о логировании
    # конкретной переменной, которой не хватает, был задан именно в теле
    # функции check_tokens(), поэтому перенесено в функцию.
    [logger.critical(f'Отсутствует переменная окружения: {token_name}')
     for token_name, token in TOKENS.items() if token is None
     ]
    # Рефакторинг
    return all(TOKENS.values())


def main():
    """Делает запрос к API, проверяет ответы, при наличии обновления —...
    получает статус работы из обновления и отправляет сообщение в Telegram,
    повторяет действия спустя RETRY_TIME, логирует работу
    (настройки логирования) в log_config.py.
    """
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
        # Необходимый try-else, чтобы после того, как действия будут успешны,
        # обнулить кэш ошибок.
        else:
            errors_cache = -1

        finally:
            if (not(message == NO_CHANGE_MESSAGE) and (errors_cache <= 0)
               and (len(message) < 5000)):
                send_message(bot=bot, message=message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
