import asyncio
import logging
from bot import main

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='bot.log'  # Логи будут сохраняться в файл
    )
    
    # Запуск бота
    asyncio.run(main()) 