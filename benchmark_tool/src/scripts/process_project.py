#!/usr/bin/env python3
"""
Скрипт для клонирования и обработки репозиториев Python проектов.

Этот скрипт позволяет клонировать Git-репозиторий, 
анализировать его код с использованием CodeProcessor 
и создавать датасет примеров для бенчмарка.
"""
import os
import sys
import argparse
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import git

# Добавляем корневую директорию проекта в путь для импорта
sys.path.append(str(Path(__file__).parent.parent))

from code_processor import CodeProcessor
from dataset.dataset import BenchmarkDataset
from utils.logging_utils import setup_logger

# Настраиваем логгер
logger = setup_logger("process_project")


def clone_repository(repo_url: str, target_dir: str, branch: str = None) -> bool:
    """
    Клонирует репозиторий по URL в указанную директорию.
    
    Args:
        repo_url: URL Git-репозитория
        target_dir: Целевая директория для клонирования
        branch: Ветка для клонирования (опционально)
        
    Returns:
        True, если клонирование успешно, иначе False
    """
    try:
        logger.info(f"Клонирование репозитория {repo_url} в {target_dir}")
        
        # Создаем директорию, если её нет
        os.makedirs(target_dir, exist_ok=True)
        
        # Проверяем, пуста ли директория
        if os.listdir(target_dir):
            logger.warning(f"Директория {target_dir} не пуста, очищаем...")
            shutil.rmtree(target_dir)
            os.makedirs(target_dir)
        
        # Клонируем репозиторий
        clone_args = ['--single-branch']
        if branch:
            clone_args.extend(['--branch', branch])
        
        git.Repo.clone_from(repo_url, target_dir, multi_options=clone_args)
        
        logger.info(f"Репозиторий успешно клонирован в {target_dir}")
        return True
    
    except git.GitCommandError as e:
        logger.error(f"Ошибка клонирования Git: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Ошибка при клонировании репозитория: {e}")
        return False


def process_project(project_dir: str, config: Dict[str, Any], output_dir: str) -> Optional[str]:
    """
    Запускает обработку всего проекта.
    
    Args:
        project_dir: Директория с проектом
        config: Конфигурация для обработки
        output_dir: Директория для сохранения результатов
        
    Returns:
        Путь к созданному датасету или None в случае ошибки
    """
    try:
        logger.info(f"Начало обработки проекта: {project_dir}")
        
        # Создаем экземпляр CodeProcessor с переданной конфигурацией
        config['project_root'] = project_dir
        config['output_dir'] = output_dir
        processor = CodeProcessor(config)
        
        # Создаем датасет
        dataset = BenchmarkDataset(name=os.path.basename(project_dir))
        
        # Получаем все Python файлы в проекте
        py_files = []
        for root, _, files in os.walk(project_dir):
            for file in files:
                if file.endswith('.py'):
                    py_files.append(os.path.join(root, file))
        
        logger.info(f"Найдено {len(py_files)} Python файлов для обработки")
        
        # Обрабатываем каждый файл
        for file_path in py_files:
            try:
                examples = processor.process_file(file_path)
                
                # Добавляем примеры в датасет
                for example in examples:
                    benchmark_example = processor.generate_example(
                        example['original_code'],
                        example['transformed_code'],
                        example['metadata'],
                        {"context": example.get('context', '')}
                    )
                    dataset.add_example(benchmark_example)
                
                logger.info(f"Обработан файл: {file_path}, добавлено {len(examples)} примеров")
            
            except Exception as e:
                logger.error(f"Ошибка при обработке файла {file_path}: {e}")
                continue
        
        # Сохраняем датасет
        if len(dataset) > 0:
            dataset_path = dataset.save_to_disk(output_dir)
            logger.info(f"Датасет сохранен в {dataset_path}, всего примеров: {len(dataset)}")
            
            # Создаем разделение на выборки, если примеров достаточно
            if len(dataset) >= 10:  # Минимальное количество для разделения
                try:
                    train_ds, val_ds, test_ds = dataset.split_dataset(0.7, 0.15, 0.15)
                    
                    # Сохраняем разделенные датасеты
                    train_path = train_ds.save_to_disk(output_dir)
                    val_path = val_ds.save_to_disk(output_dir)
                    test_path = test_ds.save_to_disk(output_dir)
                    
                    logger.info(f"Датасет разделен на выборки: train({len(train_ds)}), val({len(val_ds)}), test({len(test_ds)})")
                except Exception as e:
                    logger.error(f"Ошибка при разделении датасета: {e}")
            
            return dataset_path
        else:
            logger.warning("Не было создано ни одного примера")
            return None
    
    except Exception as e:
        logger.error(f"Ошибка при обработке проекта: {e}")
        return None


def main():
    """
    Основная функция запуска с аргументами командной строки.
    """
    parser = argparse.ArgumentParser(description="Клонирование и обработка Python проекта")
    
    # Аргументы для клонирования
    parser.add_argument("--repo", help="URL Git-репозитория для клонирования")
    parser.add_argument("--branch", help="Ветка Git для клонирования")
    
    # Аргументы для обработки
    parser.add_argument("--project-dir", required=True, help="Путь к директории с проектом (уже клонированным или локальным)")
    parser.add_argument("--config", default="config.json", help="Путь к файлу конфигурации")
    parser.add_argument("--output-dir", default="datasets", help="Директория для сохранения результатов")
    
    args = parser.parse_args()
    
    # Загружаем конфигурацию
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке конфигурации: {e}")
        sys.exit(1)
    
    # Клонируем репозиторий, если указан URL
    if args.repo:
        project_dir = args.project_dir
        if not clone_repository(args.repo, project_dir, args.branch):
            logger.error("Не удалось клонировать репозиторий, завершение работы")
            sys.exit(1)
    else:
        # Проверяем существование указанной директории
        if not os.path.exists(args.project_dir):
            logger.error(f"Директория проекта не существует: {args.project_dir}")
            sys.exit(1)
        project_dir = args.project_dir
    
    # Создаем директорию для выходных данных
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Обрабатываем проект
    result_path = process_project(project_dir, config, args.output_dir)
    
    if result_path:
        logger.info(f"Обработка завершена успешно. Результаты сохранены в {result_path}")
        sys.exit(0)
    else:
        logger.error("Обработка завершилась с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
