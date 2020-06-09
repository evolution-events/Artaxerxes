import logging


class Ignore404(logging.Filter):
    def filter(self, record):
        return getattr(record, 'status_code', None) != 404
