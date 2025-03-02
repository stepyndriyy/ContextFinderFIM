"""
Основной модуль для обработки кода и применения трансформаций.

Включает функциональность для анализа, трансформации и генерации примеров.
"""
import os
import ast    
import argparse
import json
import random
from typing import Dict, Any, List, Optional, Tuple

import benchmark_tool.src.ast_parser as ast_parser
from benchmark_tool.src.transformers.base import TransformerRegistry
from benchmark_tool.src.utils.logging_utils import setup_logger
from src.code_context_collector import CodeContextCollector

from benchmark_tool.src.transformers.function_calls import FunctionCallRemover
from benchmark_tool.src.transformers.imports import ImportOptimizer
from benchmark_tool.src.transformers.function_body import FunctionBodyRemover


# Настраиваем логгер
logger = setup_logger("code_processor")


class CodeProcessor:
    """
    Основной класс для обработки кода.
    
    Отвечает за:
    - Анализ кода и выбор подходящих трансформаций
    - Применение трансформаций
    - Сбор контекста и генерацию примеров для датасета
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация процессора с конфигурацией.
        
        Args:
            config: Конфигурация процессора и трансформаторов
        """
        self.config = config
        self.transformers_config = config.get('transformers', {})
        self.context_level = config.get('context_level', 'local')
        self.output_dir = config.get('output_dir', 'output')
        self.max_transformations = config.get('max_transformations_per_file', 1)
        
        # Создаем экземпляры трансформаторов из конфигурации
        self.transformers = []
        for name, tf_config in self.transformers_config.items():
            if tf_config.get('enabled', True):
                transformer = TransformerRegistry.get_transformer(name, tf_config)
                if transformer:
                    self.transformers.append(transformer)
                else:
                    logger.warning(f"Трансформатор '{name}' не найден в реестре.")
        
        # Инициализируем сборщик контекста
        self.context_collector = CodeContextCollector(
            project_root=config.get('project_root'),
            max_file_size=config.get('max_file_size', 1_000_000)
        )
        
        # Создаем выходную директорию, если её нет
        os.makedirs(self.output_dir, exist_ok=True)
    
    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Обрабатывает один файл, применяя трансформации и генерируя примеры.
        
        Args:
            file_path: Путь к обрабатываемому файлу
            
        Returns:
            Список сгенерированных примеров
        """
        logger.info(f"Обработка файла: {file_path}")
        
        # Парсим файл в AST
        ast_tree = ast_parser.parse_file(file_path)
        if not ast_tree:
            logger.error(f"Не удалось распарсить файл: {file_path}")
            return []
        
        # Получаем исходный код
        with open(file_path, 'r', encoding='utf-8') as f:
            original_code = f.read()
        
        examples = []
        transformations_applied = 0
        
        # Пытаемся применить несколько разных трансформаций
        while transformations_applied < self.max_transformations:
            # Выбираем трансформацию
            transformation = self.select_transformation(ast_tree)
            if not transformation:
                logger.info(f"Не найдено подходящих трансформаций для {file_path}")
                break
            
            # Применяем трансформацию
            transformed_code, metadata = self.apply_transformation(original_code, file_path, transformation)
            
            # Если трансформация применена успешно, генерируем пример
            if metadata.get('success', False):
                # Собираем контекст кода
                context = self.collect_context(file_path)
                
                # Создаем пример
                # relative_path = os.path.relpath(file_path, self.config.get('project_root', '.'))
                example = self.generate_example(original_code, transformed_code, metadata, context, file_path)
                examples.append(example)
                
                transformations_applied += 1
                logger.info(f"Применена трансформация {transformation.__class__.__name__} к {file_path}")
            else:
                logger.info(f"Трансформация {transformation.__class__.__name__} не удалась: {metadata.get('reason', 'Неизвестная причина')}")
                # Пробуем другую трансформацию
                continue
        
        return examples
    
    def select_transformation(self, ast_tree: ast.Module) -> Optional[Any]:
        """
        Выбирает подходящую трансформацию для данного AST дерева.
        
        Args:
            ast_tree: AST дерево для анализа
            
        Returns:
            Экземпляр подходящего трансформатора или None
        """
        # Перемешиваем трансформаторы для случайного выбора
        random.shuffle(self.transformers)
        
        # Проверяем каждый трансформатор
        for transformer in self.transformers:
            # Проверяем, может ли трансформатор быть применен к этому AST
            can_apply = False
            
            # Для разных типов трансформаторов нужны разные проверки
            # Например, для трансформатора функций нужно проверить наличие подходящих функций
            if transformer.__class__.__name__ == 'FunctionBodyRemover':
                functions, methods = ast_parser.find_functions(ast_tree)
                can_apply = any(transformer.can_transform(f) for f in functions + methods)
            
            # Для трансформатора вызовов функций нужно проверить наличие вызовов
            elif transformer.__class__.__name__ == 'FunctionCallRemover':
                calls = ast_parser.find_function_calls(ast_tree)
                can_apply = any(transformer.can_transform(call) for call in calls)
            
            # Для оптимизатора импортов всегда можно применить, если есть импорты
            elif transformer.__class__.__name__ == 'ImportOptimizer':
                imports, from_imports = ast_parser.find_imports(ast_tree)
                can_apply = bool(imports or from_imports)
            
            # Для других трансформаторов могут быть другие проверки
            else:
                # Общая проверка - есть ли узлы, которые можно трансформировать
                for node in ast.walk(ast_tree):
                    if transformer.can_transform(node):
                        can_apply = True
                        break
            
            # Если трансформатор может быть применен, возвращаем его
            if can_apply:
                return transformer
        
        # Если не нашли подходящий трансформатор
        return None
    
    def apply_transformation(self, code: str, file_path: str, transformer: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Применяет трансформацию к коду.
    
        Args:
            code: Исходный код
            file_path: Путь к файлу (для логирования)
            transformer: Экземпляр трансформатора
        
        Returns:
            Кортеж из трансформированного кода и метаданных
        """
        try:
            transformed_code, metadata = transformer.apply_transformation(code, file_path)
        
            # More detailed logging
            if metadata.get("success", False):
                logger.info(f"Transformation {transformer.__class__.__name__} applied successfully.")
            else:
                logger.warning(f"Transformation {transformer.__class__.__name__} failed: {metadata.get('reason', 'Unknown reason')}")
            
            return transformed_code, metadata
        except Exception as e:
            import traceback
            logger.error(f"Error applying transformation {transformer.__class__.__name__}: {e}")
            logger.debug(traceback.format_exc())
            return code, {"success": False, "error": str(e)}    

    def collect_context(self, file_path: str) -> Dict[str, str]:
        """
        Собирает контекст кода из файла и связанных импортов.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Словарь с контекстом кода
        """
        try:
            # Используем CodeContextCollector для сбора контекста
            context = self.context_collector.collect_context(file_path)
            formatted_context = self.context_collector.format_context()
            return {"context": formatted_context}
        except Exception as e:
            logger.error(f"Ошибка при сборе контекста для {file_path}: {e}")
            return {"context": "", "error": str(e)}
    
    def generate_example(self, original: str, transformed: str, metadata: Dict[str, Any], context: Dict[str, str], file_path: str) -> Dict[str, Any]:
        """
        Создает пример для датасета на основе оригинального и трансформированного кода.
    
        Args:
            original: Оригинальный код
            transformed: Трансформированный код
            metadata: Метаданные о трансформации
            context: Контекст кода
            file_path: Путь к файлу относительно корня проекта
        
        Returns:
            Словарь с примером для датасета
        """
        # Формируем задание для модели
        task_description = self._generate_task_description(metadata)
    
        # Создаем пример с дополнительными данными для FIM
        example = {
            "original_code": original,
            "transformed_code": transformed,
            "task_description": task_description,
            "transformation_type": metadata.get('type', 'unknown'),
            "metadata": metadata,
            "context": context.get('context', ''),
            "file_path": file_path  # Добавляем путь к файлу
        }
    
        # Для FIM добавляем информацию о курсоре
        if metadata.get('type') == 'function_body_removal':
            example.update({
                "function_name": metadata.get("function_name", ""),
                "removed_body": metadata.get("removed_body", ""),
                "fim_cursor_line": metadata.get("fim_cursor_line", 0),
                "fim_cursor_column": metadata.get("fim_cursor_column", 0),
                "fim_cursor_position": metadata.get("fim_cursor_position", 0)
            })
    
        return example
    
    def _generate_task_description(self, metadata: Dict[str, Any]) -> str:
        """
        Генерирует описание задачи для модели на основе метаданных трансформации.
        
        Args:
            metadata: Метаданные о трансформации
            
        Returns:
            Строка с описанием задачи
        """
        transformation_type = metadata.get('type')
        
        if transformation_type == 'function_body_removal':
            function_name = metadata.get('function_name', 'unknown')
            return f"Заполните тело функции {function_name}, которое было удалено."
        
        elif transformation_type == 'function_call_removal':
            calls = metadata.get('replaced_calls', [])
            if calls:
                call_descriptions = ", ".join([call.get('function_name', 'unknown') for call in calls])
                return f"Восстановите вызовы функций, которые были удалены: {call_descriptions}."
            return "Восстановите удаленные вызовы функций."
        
        elif transformation_type == 'import_optimization':
            return "Восстановите импорты, которые были удалены или оптимизированы."
        
        # Для других типов трансформаций
        return "Восстановите код, который был трансформирован."
    
    def save_examples(self, examples: List[Dict[str, Any]], output_file: str = None) -> str:
        """
        Сохраняет сгенерированные примеры в JSON файл.
        
        Args:
            examples: Список примеров
            output_file: Имя выходного файла (опционально)
            
        Returns:
            Путь к сохраненному файлу
        """
        if not output_file:
            output_file = os.path.join(self.output_dir, f"examples_{len(examples)}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(examples, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Сохранены {len(examples)} примеров в {output_file}")
        return output_file
    
    def process_directory(self, directory: str, output_file: str = None) -> str:
        """
        Обрабатывает все Python файлы в директории.
        
        Args:
            directory: Путь к директории
            output_file: Имя выходного файла (опционально)
            
        Returns:
            Путь к сохраненному файлу с примерами
        """
        all_examples = []
        
        # Рекурсивно перебираем все .py файлы в директории
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    # Обрабатываем файл
                    examples = self.process_file(file_path)
                    if examples:
                        all_examples.extend(examples)
        for example in examples:
            print(example['file_path'])
        # Сохраняем примеры
        return self.save_examples(all_examples, output_file)


# Пример использования
if __name__ == "__main__":
    # Регистрируем трансформаторы
    TransformerRegistry.register("function_call", FunctionCallRemover)
    TransformerRegistry.register("import_optimizer", ImportOptimizer)
    TransformerRegistry.register("function_body", FunctionBodyRemover)
        
    parser = argparse.ArgumentParser(description="Обработчик кода для генерации примеров")
    parser.add_argument("--config", default="config.json", help="Путь к файлу конфигурации")
    parser.add_argument("--input", required=True, help="Путь к файлу или директории для обработки")
    parser.add_argument("--output", help="Путь для сохранения примеров")
    
    args = parser.parse_args()
    
    # Загружаем конфигурацию
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Файл конфигурации {args.config} не найден.")
        config = {
            "transformers": {
                "function_body": {"enabled": True, "probability": 0.7},
                # "function_call": {"enabled": True, "probability": 0.5},
                # "import_optimizer": {"enabled": True, "probability": 0.3}
            },
            "output_dir": "generated_examples",
            "max_transformations_per_file": 2
        }
        print("Используется конфигурация по умолчанию.")
    
    # Создаем процессор
    processor = CodeProcessor(config)
    
    # Обрабатываем ввод
    if os.path.isfile(args.input):
        # Обработка одного файла
        examples = processor.process_file(args.input)
        processor.save_examples(examples, args.output)
    elif os.path.isdir(args.input):
        # Обработка директории
        output_path = processor.process_directory(args.input, args.output)
        print(f"Примеры сохранены в {output_path}")
    else:
        print(f"Путь {args.input} не найден.")