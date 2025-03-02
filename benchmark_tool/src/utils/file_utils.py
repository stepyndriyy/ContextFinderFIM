"""
Утилиты для работы с файлами и директориями.
"""
import os
import glob
from pathlib import Path
from typing import List, Optional


def find_python_files(directory: str) -> List[str]:
    """
    Рекурсивный поиск всех Python файлов в директории.
    
    Args:
        directory: Путь к директории для поиска
        
    Returns:
        Список путей к Python файлам
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория {directory} не найдена")
    
    python_files = []
    for root, _, _ in os.walk(directory):
        # Используем glob для поиска всех .py файлов в текущей директории
        files = glob.glob(os.path.join(root, "*.py"))
        python_files.extend(files)
    
    return sorted(python_files)


def read_file(path: str) -> Optional[str]:
    """
    Чтение содержимого файла с обработкой ошибок.
    
    Args:
        path: Путь к файлу
        
    Returns:
        Содержимое файла или None, если файл не удалось прочитать
    """
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Ошибка при чтении файла {path}: {e}")
        return None


def write_file(path: str, content: str) -> bool:
    """
    Запись содержимого в файл с созданием необходимых директорий.
    
    Args:
        path: Путь к файлу
        content: Содержимое для записи
        
    Returns:
        True, если запись успешна, False в противном случае
    """
    try:
        # Создаем директории при необходимости
        ensure_directory(os.path.dirname(path))
        
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
        return True
    except Exception as e:
        print(f"Ошибка при записи в файл {path}: {e}")
        return False


def ensure_directory(path: str) -> bool:
    """
    Создание директории, если она не существует.
    
    Args:
        path: Путь к директории
        
    Returns:
        True, если директория существует или была создана, False в противном случае
    """
    if not path:  # Проверка на пустой путь
        return True
    
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Ошибка при создании директории {path}: {e}")
        return False
