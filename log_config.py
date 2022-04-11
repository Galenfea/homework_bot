import sys

log_config = {
    'version': 1,
    'handlers': {
        'homework_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'homework_formatter',
            'stream': sys.stdout
        },
    },
    'loggers': {
        'homework': {
            'handlers': ['homework_handler'],
            'level': 'DEBUG',
        }
    },
    'formatters': {
        'homework_formatter': {
            'format': '%(asctime)s [%(levelname)s] %(message)s'
        }
    }
}
