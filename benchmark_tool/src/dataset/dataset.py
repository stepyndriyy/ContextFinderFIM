"""
Модуль для работы с датасетом бенчмарка.

Включает класс BenchmarkDataset для управления коллекцией примеров,
их разделения на выборки и сохранения/загрузки.
"""
import os
import json
import random
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime

from benchmark_tool.src.dataset.example import BenchmarkExample


class BenchmarkDataset:
    """
    Класс для работы с датасетом бенчмарка.
    
    Представляет коллекцию примеров и предоставляет операции над ней:
    добавление примеров, разделение на выборки, сохранение и загрузка.
    """
    
    def __init__(self, name: str = "code_benchmark"):
        """
        Инициализирует датасет.
        
        Args:
            name: Имя датасета
        """
        self.name = name
        self.examples = []
        self.metadata = {
            "name": name,
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "examples_count": 0,
            "transformation_types": {}
        }
    
    def add_example(self, example: Union[BenchmarkExample, Dict[str, Any]]) -> None:
        """
        Добавляет пример в датасет.
        
        Args:
            example: Экземпляр BenchmarkExample или словарь с данными примера
        """
        if isinstance(example, dict):
            example = BenchmarkExample.from_dict(example)
        
        self.examples.append(example)
        
        # Обновляем метаданные
        self.metadata["examples_count"] = len(self.examples)
        
        # Обновляем статистику по типам трансформаций
        transformation_type = example.metadata.get('type', 'unknown')
        if transformation_type in self.metadata["transformation_types"]:
            self.metadata["transformation_types"][transformation_type] += 1
        else:
            self.metadata["transformation_types"][transformation_type] = 1
    
    def split_dataset(self, train_ratio: float = 0.8, val_ratio: float = 0.1, 
                     test_ratio: float = 0.1) -> Tuple['BenchmarkDataset', 'BenchmarkDataset', 'BenchmarkDataset']:
        """
        Разделяет датасет на обучающую, валидационную и тестовую выборки.
        
        Args:
            train_ratio: Доля примеров для обучающей выборки
            val_ratio: Доля примеров для валидационной выборки
            test_ratio: Доля примеров для тестовой выборки
            
        Returns:
            Кортеж из трех датасетов (train, val, test)
        """
        # Проверяем, что пропорции корректны
        total_ratio = train_ratio + val_ratio + test_ratio
        if not (0.99 <= total_ratio <= 1.01):  # Допускаем небольшую погрешность из-за float
            raise ValueError(f"Сумма пропорций должна быть равна 1.0, получено {total_ratio}")
        
        # Перемешиваем примеры для равномерного распределения
        shuffled_examples = self.examples.copy()
        random.shuffle(shuffled_examples)
        
        # Определяем границы выборок
        num_examples = len(shuffled_examples)
        train_end = int(num_examples * train_ratio)
        val_end = train_end + int(num_examples * val_ratio)
        
        # Создаем датасеты
        train_dataset = BenchmarkDataset(f"{self.name}_train")
        val_dataset = BenchmarkDataset(f"{self.name}_val")
        test_dataset = BenchmarkDataset(f"{self.name}_test")
        
        # Распределяем примеры
        for example in shuffled_examples[:train_end]:
            train_dataset.add_example(example)
        
        for example in shuffled_examples[train_end:val_end]:
            val_dataset.add_example(example)
        
        for example in shuffled_examples[val_end:]:
            test_dataset.add_example(example)
        
        return train_dataset, val_dataset, test_dataset
    
    def save_to_disk(self, output_dir: str) -> str:
        """
        Сохраняет датасет на диск.
        
        Args:
            output_dir: Директория для сохранения
            
        Returns:
            Путь к директории с сохраненным датасетом
        """
        # Создаем директорию
        dataset_dir = Path(output_dir) / self.name
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Сохраняем каждый пример в отдельный файл
        examples_dir = dataset_dir / "examples"
        os.makedirs(examples_dir, exist_ok=True)
        
        for example in self.examples:
            example_path = examples_dir / f"{example.id}.json"
            with open(example_path, 'w', encoding='utf-8') as f:
                json.dump(example.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Обновляем метаданные и сохраняем их
        self.metadata["updated_at"] = datetime.now().isoformat()
        self.metadata["examples_count"] = len(self.examples)
        
        metadata_path = dataset_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        
        return str(dataset_dir)
    
    @classmethod
    def load_from_disk(cls, input_dir: str) -> 'BenchmarkDataset':
        """
        Загружает датасет с диска.
        
        Args:
            input_dir: Директория с сохраненным датасетом
            
        Returns:
            Загруженный датасет
        """
        dataset_dir = Path(input_dir)
        
        # Загружаем метаданные
        metadata_path = dataset_dir / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Файл метаданных не найден: {metadata_path}")
            
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Создаем датасет
        dataset = cls(name=metadata["name"])
        dataset.metadata = metadata
        
        # Загружаем примеры
        examples_dir = dataset_dir / "examples"
        if not examples_dir.exists():
            raise FileNotFoundError(f"Директория с примерами не найдена: {examples_dir}")
            
        for example_file in examples_dir.glob("*.json"):
            with open(example_file, 'r', encoding='utf-8') as f:
                example_data = json.load(f)
                dataset.add_example(example_data)
        
        return dataset
    
    def get_examples_by_type(self, transformation_type: str) -> List[BenchmarkExample]:
        """
        Возвращает примеры с определенным типом трансформации.
        
        Args:
            transformation_type: Тип трансформации
            
        Returns:
            Список примеров
        """
        return [ex for ex in self.examples if ex.metadata.get('type') == transformation_type]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Возвращает статистику по датасету.
        
        Returns:
            Словарь со статистикой
        """
        stats = {
            "total_examples": len(self.examples),
            "transformation_types": self.metadata["transformation_types"],
            "name": self.name,
            "created_at": self.metadata.get("created_at"),
            "updated_at": self.metadata.get("updated_at")
        }
        
        return stats
    
    def merge(self, other_dataset: 'BenchmarkDataset') -> 'BenchmarkDataset':
        """
        Объединяет текущий датасет с другим.
        
        Args:
            other_dataset: Другой датасет для объединения
            
        Returns:
            Новый объединенный датасет
        """
        merged_dataset = BenchmarkDataset(f"{self.name}_merged")
        
        # Добавляем примеры из текущего датасета
        for example in self.examples:
            merged_dataset.add_example(example)
        
        # Добавляем примеры из другого датасета
        for example in other_dataset.examples:
            merged_dataset.add_example(example)
        
        return merged_dataset
    
    def filter(self, condition) -> 'BenchmarkDataset':
        """
        Создает новый датасет, содержащий только примеры, удовлетворяющие условию.
        
        Args:
            condition: Функция, принимающая пример и возвращающая булево значение
            
        Returns:
            Отфильтрованный датасет
        """
        filtered_dataset = BenchmarkDataset(f"{self.name}_filtered")
        
        for example in self.examples:
            if condition(example):
                filtered_dataset.add_example(example)
        
        return filtered_dataset
    
    def __len__(self) -> int:
        """
        Возвращает количество примеров в датасете.
        
        Returns:
            Количество примеров
        """
        return len(self.examples)
    
    def __getitem__(self, idx) -> BenchmarkExample:
        """
        Получает пример по индексу.
        
        Args:
            idx: Индекс примера
            
        Returns:
            Пример с указанным индексом
        """
        return self.examples[idx]
