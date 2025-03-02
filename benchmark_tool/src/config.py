"""
Модуль для работы с конфигурацией бенчмарка.
"""
import os
import yaml
from typing import Dict, Any, Optional
from utils.file_utils import read_file, ensure_directory


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Загрузка конфигурации из YAML файла.
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Словарь с настройками
    """
    content = read_file(config_path)
    if not content:
        raise ValueError(f"Не удалось прочитать файл конфигурации: {config_path}")
    
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Ошибка парсинга YAML: {e}")


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Проверка корректности конфигурации.
    
    Args:
        config: Словарь с настройками
        
    Returns:
        True, если конфигурация валидна, иначе False
    """
    required_sections = ['project', 'transformations', 'dataset']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Отсутствует обязательная секция в конфигурации: {section}")
    
    # Проверка секции project
    project_section = config['project']
    if 'name' not in project_section or 'target_dir' not in project_section:
        raise ValueError("В секции 'project' отсутствуют обязательные поля: name и/или target_dir")
    
    # Проверка секции transformations
    transformations = config['transformations']
    if not transformations:
        raise ValueError("Секция 'transformations' пуста")
    
    for transform_name, transform_config in transformations.items():
        if 'enabled' not in transform_config:
            raise ValueError(f"В конфигурации трансформации {transform_name} отсутствует поле 'enabled'")
    
    # Проверка секции dataset
    dataset_section = config['dataset']
    if 'output_dir' not in dataset_section:
        raise ValueError("В секции 'dataset' отсутствует обязательное поле: output_dir")
    
    # Проверяем, что сумма долей для разбиения на выборки равна 1
    splits = ['train_split', 'val_split', 'test_split']
    if all(split in dataset_section for split in splits):
        total_split = sum(dataset_section[split] for split in splits)
        if not (0.99 <= total_split <= 1.01):  # Проверка с погрешностью
            raise ValueError(f"Сумма долей разбиения датасета должна быть равна 1, текущая сумма: {total_split}")
    
    return True


def get_transformation_settings(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Получение настроек трансформаций из конфигурации.
    
    Args:
        config: Словарь с конфигурацией или None для загрузки из файла
        
    Returns:
        Словарь с настройками трансформаций
    """
    if config is None:
        config_path = os.environ.get("BENCHMARK_CONFIG", "config.yaml")
        config = load_config(config_path)
    
    validate_config(config)
    return config['transformations']


def get_dataset_settings(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Получение настроек датасета из конфигурации.
    
    Args:
        config: Словарь с конфигурацией или None для загрузки из файла
        
    Returns:
        Словарь с настройками датасета
    """
    if config is None:
        config_path = os.environ.get("BENCHMARK_CONFIG", "config.yaml")
        config = load_config(config_path)
    
    validate_config(config)
    return config['dataset']


def get_project_settings(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Получение настроек проекта из конфигурации.
    
    Args:
        config: Словарь с конфигурацией или None для загрузки из файла
        
    Returns:
        Словарь с настройками проекта
    """
    if config is None:
        config_path = os.environ.get("BENCHMARK_CONFIG", "config.yaml")
        config = load_config(config_path)
    
    validate_config(config)
    return config['project']