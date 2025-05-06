import os
import sys
import subprocess
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='restart.log'
)

def restart_bot():
    try:
        # Получаем путь к текущей директории
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Активируем виртуальное окружение и запускаем бота
        command = f"cd {current_dir} && workon mybot && python run_bot.py"
        
        # Запускаем процесс
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logging.info("Бот успешно перезапущен")
        
    except Exception as e:
        logging.error(f"Ошибка при перезапуске бота: {e}")

if __name__ == "__main__":
    restart_bot() 