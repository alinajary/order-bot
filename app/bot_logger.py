import logging
import os
class BotLogger:
    def __init__(self, log_file:str = "bot.log", level = logging.INFO):
        
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_file):
            os.makedirs(log_dir, exist_ok=True)
            
        logging.basicConfig(
            format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level = level,
            filename = log_file,
            filemode = 'a'  # Append mode
        )
        self.logger = logging.getLogger("BotLogger")
        
    def info(self, message:str):
        self.logger.info(message)

    def warning(self, message:str):
        self.logger.warning(message)

    def error(self, message:str):
        self.logger.error(message)

    def debug(self, message:str):
        self.logger.debug(message)