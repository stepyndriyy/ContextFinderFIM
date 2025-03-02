"""
Утилиты для настройки логирования и записи логов.
"""
import logging
import sys
import os
from typing import Dict, Any, Optional
import difflib

# Создаем директорию для логов, если она не существует
os.makedirs('logs', exist_ok=True)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Настройка логгера с форматированием.
    
    Args:
        name: Имя логгера
        level: Уровень логирования (по умолчанию INFO)
        
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Проверяем, есть ли уже обработчики, чтобы избежать дублирования
    if not logger.handlers:
        # Обработчик для записи в файл
        file_handler = logging.FileHandler(f"logs/{name}.log")
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Обработчик для вывода в консоль
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def log_transformation(
    original: str, 
    transformed: str, 
    transformation_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Логирование примененной трансформации.
    
    Args:
        original: Исходный код
        transformed: Трансформированный код
        transformation_type: Тип трансформации
        metadata: Дополнительная информация о трансформации
        
    Returns:
        Строка с diff между оригинальным и трансформированным кодом
    """
    logger = setup_logger('transformations')
    
    # Создаем diff между оригинальным и трансформированным кодом
    diff = list(difflib.unified_diff(
        original.splitlines(True),
        transformed.splitlines(True),
        fromfile='original',
        tofile='transformed',
        n=3  # Контекст - 3 строки
    ))
    
    diff_text = ''.join(diff)
    
    # Логируем информацию о трансформации
    logger.info(f"Применена трансформация: {transformation_type}")
    if metadata:
        logger.info(f"Метаданные: {metadata}")
    
    # Логируем diff только на уровне DEBUG
    logger.debug(f"Diff:\n{diff_text}")
    
    return diff_text