class APIError(Exception):
    '''Исключение возникает при ошибках в работе с API'''
    pass


class EnvError(Exception):
    '''Исключение возникает при ошибках, связанных с переменными окружения'''
    pass
