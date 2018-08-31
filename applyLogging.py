import logging

def get_module_logger(app_name,file_path):
        logger = logging.getLogger(app_name)
        fh = logging.FileHandler(file_path)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - process=%(name)s - status=%(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.setLevel(logging.DEBUG)
        return logger
