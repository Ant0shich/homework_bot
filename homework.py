import telegram
import requests
from dotenv import load_dotenv
import os
import logging
import time
from http import HTTPStatus
from json import JSONDecodeError
from error import TgError
load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='example.log',
    level=logging.DEBUG,
    encoding='UTF-8'
)


def check_tokens():
    """Проверяет наличие токенов."""
    logging.info('Проверка наличия всех переменных')
    is_check_tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not is_check_tokens:
        message_error = 'Отсутствие обязательных переменных окружения \
во время запуска бота'
        logging.critical(message_error)
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except telegram.TelegramError:
        message_error = f'Сообщение не удалось отправить: {message}'
        logging.error(message_error)
    except Exception:
        logging.error('Другая проблема')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        time_metka = {'from_date': timestamp}
        homework_statuses = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=time_metka
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise requests.RequestException('Запрошенный URL не '
                                            'может быть получен')
        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        raise TgError(f'Ошибка в телеграм {error} ')
    except JSONDecodeError as error:
        raise JSONDecodeError(f"Ошибка при декодировании JSON: {error}")


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('В переменной response ожидался слоаврь')
    if 'homeworks' not in response:
        raise KeyError(
            'Homework в ответе API не соответствует требованиям'
            f'ключ:{response.keys()}'
        )
    if "current_date" not in response:
        raise KeyError("Нет current_date в homeworks")
    hw = response['homeworks']
    if not isinstance(hw, list):
        raise TypeError(f'{hw} не является списком')
    if not hw:
        logging.DEBUG('Статус не изменился')
        return hw
    return hw[0]


def parse_status(homework):
    """Изменения статуса работы бота."""
    logging.debug('Формирование содержания сообщения')
    for key in ('homework_name', 'status'):
        if key not in homework:
            raise KeyError(f'Отсутствует ключ: {key}')
    homework_name = homework["homework_name"]
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Ошибка ключа')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    else:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = 0
        zero_message = ''
        while True:
            try:
                response = get_api_answer(timestamp)
                homework = check_response(response)
                logging.info("Список домашних работ получен")
                if homework:
                    status = parse_status(homework)
                    if status not in zero_message:
                        zero_message = status
                        send_message(bot, zero_message)
                        logging.info('Сообщение отправлено')
                else:
                    logging.info("Задания не обнаружены")
            except Exception as error:
                message = f"Сбой в программе: {error}"
                logging.error(message)
                if message != zero_message:
                    send_message(bot, message)
                    zero_message = message
                raise Exception(error)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
