#!/usr/bin/env python3
"""
Скрипт для генерации примеров трансформаций кода и создания датасета.

Позволяет обработать указанные файлы, применить к ним различные 
трансформации и создать датасет для обучения или тестирования моделей.
Поддерживает обработку нескольких проектов одновременно.
"""
import os
import sys
import argparse
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
import random

# Добавляем корневую директорию проекта в путь для импорта
sys.path.append(str(Path(__file__).parent.parent))

from code_processor import CodeProcessor
from dataset.dataset import BenchmarkDataset
from dataset.example import BenchmarkExample
from utils.logging_utils import setup_logger

# Настраиваем логгер
logger = setup_logger("generate_examples")


def generate_examples(processor: CodeProcessor, file_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Генерирует примеры для указанных файлов.
    
    Args:
        processor: Экземпляр CodeProcessor для обработки файлов
        file_paths: Список путей к файлам для генерации примеров
        
    Returns:
        Список сгенерированных примеров
    """
    all_examples = []
    
    logger.info(f"Начало генерации примеров для {len(file_paths)} файлов")
    
    # Перемешиваем файлы для более равномерного распределения примеров
    random.shuffle(file_paths)
    
    # Обрабатываем каждый файл
    for file_path in file_paths:
        try:
            examples = processor.process_file(file_path)
            if examples:
                all_examples.extend(examples)
                logger.info(f"Файл {file_path}: сгенерировано {len(examples)} примеров")
            else:
                logger.info(f"Файл {file_path}: не удалось сгенерировать примеры")
        except Exception as e:
            logger.error(f"Ошибка при обработке файла {file_path}: {e}")

    logger.info(f"Всего сгенерировано {len(all_examples)} примеров")
    return all_examples


def create_dataset(examples: List[Dict[str, Any]], config: Dict[str, Any]) -> BenchmarkDataset:
    """
    Создает датасет из сгенерированных примеров.
    
    Args:
        examples: Список примеров
        config: Конфигурация для создания датасета
        
    Returns:
        Созданный датасет
    """
    dataset_name = config.get("dataset_name", "code_transformations")
    dataset = BenchmarkDataset(name=dataset_name)
    
    logger.info(f"Создание датасета '{dataset_name}' из {len(examples)} примеров")
    
    # Конвертируем каждый пример в формат BenchmarkExample и добавляем в датасет
    for example in examples:
        # Основные поля примера
        original_code = example["original_code"]
        transformed_code = example["transformed_code"]
        metadata = example["metadata"]
        
        # Создаем экземпляр BenchmarkExample
        benchmark_example = BenchmarkExample(
            original=original_code,
            transformed=transformed_code,
            metadata=metadata,
            file_path=example.get("file_path", ""),
            project_root=example.get("project_root", ""),
        )
        
        # Добавляем контекст, если он есть
        if "context" in example:
            benchmark_example.add_context(example["context"], level="local")
        
        # Добавляем пример в датасет
        dataset.add_example(benchmark_example)
    
    logger.info(f"Датасет создан, содержит {len(dataset)} примеров")
    
    # Выводим статистику по типам трансформаций
    stats = dataset.get_statistics()
    logger.info("Статистика по типам трансформаций:")
    for transformation_type, count in stats["transformation_types"].items():
        logger.info(f"  {transformation_type}: {count} примеров")
    
    return dataset


def main():
    """
    Основная функция запуска.
    """
    parser = argparse.ArgumentParser(description="Генерация примеров и создание датасета")
    
    # Аргументы для входных файлов
    parser.add_argument("--files", nargs="+", help="Список файлов для обработки")
    parser.add_argument("--files-from", help="Файл со списком файлов для обработки")
    parser.add_argument("--directory", help="Директория с файлами для обработки (устаревший параметр, используйте --directories)")
    parser.add_argument("--directories", nargs="+", help="Список директорий с файлами для обработки")
    parser.add_argument("--pattern", default="*.py", help="Шаблон для поиска файлов (по умолчанию: *.py)")
    
    # Аргументы для конфигурации и вывода
    parser.add_argument("--config", default="config.json", help="Путь к файлу конфигурации")
    parser.add_argument("--output-dir", default="datasets", help="Директория для сохранения датасета")
    parser.add_argument("--dataset-name", help="Имя создаваемого датасета")
    parser.add_argument("--split", action="store_true", help="Разделить датасет на обучающую, валидационную и тестовую выборки")
    
    args = parser.parse_args()
    
    # Загружаем конфигурацию
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке конфигурации: {e}")
        sys.exit(1)
    
    # Если указано имя датасета через аргумент, переопределяем конфигурацию
    if args.dataset_name:
        config["dataset_name"] = args.dataset_name
    
    # Получаем список файлов для обработки
    file_paths = []
    
    # Обрабатываем аргумент с файлами
    if args.files:
        file_paths.extend(args.files)
    
    # Обрабатываем аргумент с файлом, содержащим список файлов
    if args.files_from:
        try:
            with open(args.files_from, 'r', encoding='utf-8') as f:
                file_paths.extend([line.strip() for line in f if line.strip()])
        except Exception as e:
            logger.error(f"Ошибка при чтении списка файлов из {args.files_from}: {e}")
    
    # Обрабатываем список директорий (новый функционал)
    directories = []
    if args.directories:
        directories.extend(args.directories)
    
    # Для обратной совместимости обрабатываем одиночную директорию
    if args.directory:
        directories.append(args.directory)
        logger.warning("Параметр --directory устарел, используйте --directories для указания нескольких директорий")
    
    # Обрабатываем каждую директорию
    for directory in directories:
        pattern = os.path.join(directory, args.pattern)
        matching_files = glob.glob(pattern, recursive=True)
        logger.info(f"В директории {directory} найдено {len(matching_files)} файлов по шаблону {args.pattern}")
        file_paths.extend(matching_files)
    
    # Проверяем, что есть файлы для обработки
    if not file_paths:
        logger.error("Не указаны файлы для обработки")
        sys.exit(1)
    
    # Фильтруем только существующие файлы
    file_paths = [path for path in file_paths if os.path.exists(path)]
    
    if not file_paths:
        logger.error("Ни один из указанных файлов не существует")
        sys.exit(1)
    
    logger.info(f"Всего найдено {len(file_paths)} файлов для обработки из {len(directories)} директорий")
    

    all_examples = []
    for directory in directories:
        logger.info(f"Обработка директории: {directory}")
        
        # Создаем копию конфигурации с обновленным project_root для текущей директории
        current_config = config.copy()
        current_config["project_root"] = directory
        
        pattern = os.path.join(directory, args.pattern)
        matching_files = glob.glob(pattern, recursive=True)
        logger.info(f"В директории {directory} найдено {len(matching_files)} файлов по шаблону {args.pattern}")
        
        if matching_files:
            # Создаем процессор с обновленной конфигурацией
            processor = CodeProcessor(current_config)
            
            # Генерируем примеры для текущей директории
            directory_examples = generate_examples(processor, matching_files)
            all_examples.extend(directory_examples)
            logger.info(f"Сгенерировано {len(directory_examples)} примеров из директории {directory}")
    
    # Общее количество примеров
    logger.info(f"Всего сгенерировано {len(all_examples)} примеров из {len(directories)} директорий")

    if not all_examples:
        logger.error("Не удалось сгенерировать примеры")
        sys.exit(1)
    
    # Создаем директорию для выходных данных
    os.makedirs(args.output_dir, exist_ok=True)
    
    logger.info(f"Создание датасета из {len(all_examples)} примеров")
    
    # Создаем датасет
    dataset = create_dataset(all_examples, config)
    
    # Сохраняем датасет
    dataset_path = dataset.save_to_disk(args.output_dir)
    logger.info(f"Датасет сохранен в {dataset_path}")
    
    # Разделяем датасет на выборки, если нужно
    if args.split and len(dataset) >= 10:  # Минимальное количество для разделения
        try:
            train_ratio = config.get("train_ratio", 0.7)
            val_ratio = config.get("val_ratio", 0.15)
            test_ratio = config.get("test_ratio", 0.15)
            
            train_ds, val_ds, test_ds = dataset.split_dataset(train_ratio, val_ratio, test_ratio)
            
            # Сохраняем разделенные датасеты
            train_path = train_ds.save_to_disk(args.output_dir)
            val_path = val_ds.save_to_disk(args.output_dir)
            test_path = test_ds.save_to_disk(args.output_dir)
            
            logger.info(f"Датасет разделен на выборки:")
            logger.info(f"  train: {len(train_ds)} примеров, сохранен в {train_path}")
            logger.info(f"  val: {len(val_ds)} примеров, сохранен в {val_path}")
            logger.info(f"  test: {len(test_ds)} примеров, сохранен в {test_path}")
        except Exception as e:
            logger.error(f"Ошибка при разделении датасета: {e}")
    
    logger.info("Генерация примеров и создание датасета завершены успешно")


if __name__ == "__main__":
    main()
