#!/usr/bin/env python3
"""
Скрипт для оценки производительности модели Fill-in-the-Middle (FIM)
с использованием датасета примеров трансформации кода.

Использует прямое обращение к CodeLlamaFIM вместо subprocess.
"""
import os
import json
import shutil
import argparse
import tempfile
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from tqdm import tqdm

# Импорт наших модулей
from code_llama_fim import CodeLlamaFIM
from src.fim_metrics import calculate_metrics
from benchmark_tool.src.dataset.dataset import BenchmarkDataset

class FIMEvaluator:
    """
    Класс для оценки эффективности модели FIM с использованием датасета.
    """
    
    def __init__(
        self,
        dataset_path: str,
        project_root: str,
        model_path: str = "codellama/CodeLlama-7b-hf",
        cache_dir: str = "models/",
        with_context: bool = True
    ):
        """
        Инициализация оценщика FIM.
        
        Args:
            dataset_path: Путь к директории датасета
            project_root: Корневая директория проекта для замены файлов
            model_path: Путь к модели CodeLlama
            cache_dir: Директория для кэширования модели
            with_context: Использовать ли контекст проекта
        """
        self.dataset_path = Path(dataset_path)
        self.project_root = Path(project_root)
        self.model_path = model_path
        self.cache_dir = cache_dir
        self.with_context = with_context
        
        # Результаты оценки
        self.results = []
        
        # Загружаем модель один раз
        print(f"Инициализация модели {model_path}...")
        self.llm = CodeLlamaFIM(
            model_path=model_path,
            cache_dir=cache_dir,
            project_root=str(project_root) if with_context else None
        )
        
        # Загружаем датасет
        print(f"Загрузка датасета из {dataset_path}...")
        self.dataset = BenchmarkDataset.load_from_disk(dataset_path)
        print(f"Загружено {len(self.dataset)} примеров")
        
    def _replace_file(self, file_path: str, new_content: str) -> Optional[str]:
        """
        Временно заменяет содержимое файла, сохраняя оригинал.
        
        Args:
            file_path: Путь к файлу для замены
            new_content: Новое содержимое файла
            
        Returns:
            Путь к временной копии оригинального файла или None в случае ошибки
        """
        # TODO подумать как нормально это сделать
        # abs_path = self.project_root / file_path
        abs_path = Path(file_path)
        
        # Проверяем, существует ли файл
        if not abs_path.exists():
            print(f"Ошибка: Файл {abs_path} не найден")
            return None
        
        try:
            # Создаем временный файл для хранения оригинала
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.close()
            
            # Копируем оригинальный файл
            shutil.copy2(abs_path, temp_file.name)
            
            # Заменяем содержимое
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return temp_file.name
        except Exception as e:
            print(f"Ошибка при замене файла {abs_path}: {e}")
            return None
    
    def _restore_file(self, file_path: str, temp_file: str) -> bool:
        """
        Восстанавливает оригинальное содержимое файла.
        
        Args:
            file_path: Путь к файлу для восстановления
            temp_file: Путь к временной копии оригинального файла
            
        Returns:
            True, если восстановление успешно, иначе False
        """
        # TODO подумать как нормально это сделать
        # abs_path = self.project_root / file_path
        abs_path = Path(file_path)
        
        try:
            # Восстанавливаем оригинальный файл
            shutil.copy2(temp_file, abs_path)
            
            # Удаляем временный файл
            os.unlink(temp_file)
            
            return True
        except Exception as e:
            print(f"Ошибка при восстановлении файла {abs_path}: {e}")
            return False
    
    def evaluate_example(self, example_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Оценивает один пример из датасета.
        
        Args:
            example_data: Словарь с данными примера
            
        Returns:
            Словарь с результатами оценки
        """
        # Получаем данные из примера
        file_path = example_data.get("file_path", "")
        if not file_path:
            print(f"Ошибка: отсутствует путь к файлу в примере {example_data.get('id', 'unknown')}")
            return {"error": "Missing file path"}
        
        transformed_code = example_data.get("transformed_code", "")
        original_code = example_data.get("original_code", "")
        removed_body = example_data.get("removed_body", "")
        cursor_position = example_data.get("fim_cursor_position", 0)
        
        # Создаем результат для этого примера
        result = {
            "id": example_data.get("id", ""),
            "function_name": example_data.get("function_name", ""),
            "file_path": file_path,
            "with_context": self.with_context
        }
        
        # Заменяем файл
        temp_file = self._replace_file(file_path, transformed_code)
        if not temp_file:
            result["error"] = "Failed to replace file"
            return result
        
        try:
            # Запускаем FIM - напрямую через класс
            # abs_path = str(self.project_root / file_path)
            abs_path = file_path
            
            start_time = time.time()
            generated_code = self.llm.complete_code(
                file_path=abs_path,
                cursor_position=cursor_position,
                max_new_tokens=150,
                temperature=0.05,
                use_project_context=self.with_context
            )
            execution_time = time.time() - start_time
            
            # Вычисляем метрики
            metrics = calculate_metrics(generated_code, removed_body)
            
            # Добавляем результаты
            result.update({
                "generated_code": generated_code,
                "original_code": removed_body,
                "execution_time": execution_time,
                **metrics
            })
            
        except Exception as e:
            import traceback
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
        
        finally:
            # Восстанавливаем оригинальный файл
            self._restore_file(file_path, temp_file)
        
        return result
    
    def evaluate_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Оценивает все примеры из датасета.
        
        Args:
            limit: Ограничение количества примеров для оценки
            
        Returns:
            Список результатов оценки
        """
        examples_count = len(self.dataset)
        if limit is not None:
            examples_count = min(limit, examples_count)
        
        examples_to_evaluate = self.dataset.examples[:examples_count]
        self.results = []
        
        print(f"Оценка {len(examples_to_evaluate)} примеров...")
        for example in tqdm(examples_to_evaluate):
            # Преобразуем пример в словарь
            example_data = example.to_dict()
            
            # Оцениваем пример
            result = self.evaluate_example(example_data)
            
            # Добавляем результат в общий список
            self.results.append(result)
        
        print(f"Оценка завершена. Оценено {len(self.results)} примеров.")
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Получает обобщенную статистику по всем оценкам.
        
        Returns:
            Словарь со статистическими данными
        """
        if not self.results:
            return {"error": "No results available"}
        
        # Фильтруем результаты без ошибок
        valid_results = [r for r in self.results if "error" not in r]
        
        if not valid_results:
            return {"error": "No valid results available"}
        
        # Вычисляем среднее значение для каждой метрики
        metrics = {}
        
        # Доступные метрики
        metric_keys = ["bleu_1", "bleu_2", "bleu_4", "rouge1_fmeasure", 
                       "rouge2_fmeasure", "rougeL_fmeasure", "levenshtein_similarity",
                       "execution_time"]
        
        for key in metric_keys:
            values = [r[key] for r in valid_results if key in r]
            if values:
                metrics[f"avg_{key}"] = sum(values) / len(values)
                metrics[f"min_{key}"] = min(values)
                metrics[f"max_{key}"] = max(values)
                metrics[f"median_{key}"] = sorted(values)[len(values) // 2]
        
        # Добавляем общую статистику
        summary = {
            "total_examples": len(self.results),
            "valid_examples": len(valid_results),
            "error_count": len(self.results) - len(valid_results),
            "error_rate": (len(self.results) - len(valid_results)) / len(self.results) if self.results else 0,
            "with_context": self.with_context,
            "model_path": self.model_path,
            "metrics": metrics
        }
        
        return summary
    
    def save_results(self, output_file: str) -> None:
        """
        Сохраняет результаты в JSON файл.
        
        Args:
            output_file: Путь к файлу для сохранения
        """
        output_path = Path(output_file)
        
        # Создаем директорию при необходимости
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Получаем общую статистику
        summary = self.get_summary()
        
        # Сохраняем полные результаты и сводку
        data = {
            "summary": summary,
            "results": self.results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Результаты сохранены в {output_path}")


def main():
    """
    Основная функция для запуска оценки из командной строки.
    """
    parser = argparse.ArgumentParser(description="Оценка FIM с контекстом")
    parser.add_argument("--dataset", required=True, help="Путь к датасету")
    parser.add_argument("--project-root", required=True, help="Корневая директория проекта")
    parser.add_argument("--model", default="codellama/CodeLlama-7b-hf", help="Путь к модели")
    parser.add_argument("--cache-dir", default="models/", help="Директория для кэширования")
    parser.add_argument("--no-context", action="store_true", help="Запуск без контекста")
    parser.add_argument("--output", default="results.json", help="Выходной файл с результатами")
    parser.add_argument("--limit", type=int, help="Ограничение количества примеров")
    
    args = parser.parse_args()
    
    # Инициализируем оценщик
    evaluator = FIMEvaluator(
        dataset_path=args.dataset,
        project_root=args.project_root,
        model_path=args.model,
        cache_dir=args.cache_dir,
        with_context=not args.no_context
    )
    
    # Оцениваем все примеры
    evaluator.evaluate_all(limit=args.limit)
    
    # Сохраняем результаты
    evaluator.save_results(args.output)
    
    # Выводим сводку
    summary = evaluator.get_summary()
    
    print("\nСводка результатов:")
    if "metrics" in summary:
        metrics = summary["metrics"]
        print(f"Среднее BLEU-4: {metrics.get('avg_bleu_4', 'N/A'):.4f}")
        print(f"Среднее сходство по Левенштейну: {metrics.get('avg_levenshtein_similarity', 'N/A'):.4f}")
        print(f"Среднее время выполнения: {metrics.get('avg_execution_time', 'N/A'):.2f} с")
    
    # print(f"Общее количество примеров: {summary['total_examples']}")
    # print(f"Успешно оценено: {summary['valid_examples']}")
    # print(f"Количество ошибок: {summary['error_count']}")
    print(summary)
    print(f"Полные результаты сохранены в {args.output}")


if __name__ == "__main__":
    main()