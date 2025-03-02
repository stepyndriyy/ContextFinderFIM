"""
Модуль для представления и работы с примерами в датасете.

Включает класс BenchmarkExample для хранения и манипулирования
примерами кода и их трансформациями.
"""
from typing import Dict, Any, List, Optional, Union
import json
import hashlib
from datetime import datetime


class BenchmarkExample:
    """
    Класс, представляющий один пример в датасете для бенчмарка.
    
    Хранит оригинальный и трансформированный код, метаданные о трансформации
    и контекст разных уровней.
    """
    def __init__(self, original: str, transformed: str, metadata: Dict[str, Any], file_path: str):
        """
        Инициализирует пример.
        
        Args:
            original: Оригинальный код
            transformed: Трансформированный код
            metadata: Метаданные о трансформации
            file_path: Путь к файлу относительно корня проекта
        """
        self.original_code = original
        self.transformed_code = transformed
        self.metadata = metadata
        self.file_path = file_path
        self.context = {}
        self.id = self._generate_id()
        self.created_at = datetime.now().isoformat()
    
    def add_context(self, context: str, level: str = 'local'):
        """
        Добавляет контекст определенного уровня к примеру.
        
        Args:
            context: Строка с контекстом
            level: Уровень контекста ('local', 'module', 'project')
        """
        self.context[level] = context
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует пример в словарь для сериализации.
        
        Returns:
            Словарь с данными примера
        """
        result = {
            'id': self.id,
            'file_path': self.file_path,  # Добавляем путь к файлу
            'original_code': self.original_code,
            'transformed_code': self.transformed_code,
            'metadata': self.metadata,
            'context': self.context,
            'created_at': self.created_at,
            'transformation_type': self.metadata.get('type', 'unknown')
        }
        
        # Добавляем дополнительные удобные поля для FIM задачи
        if self.metadata.get('type') == 'function_body_removal':
            result.update({
                'removed_body': self.metadata.get('removed_body', ''),
                'function_name': self.metadata.get('function_name', ''),
                'original_body_start_line': self.metadata.get('original_body_start_line', 0),
                'original_body_end_line': self.metadata.get('original_body_end_line', 0),
                'transformed_body_start_line': self.metadata.get('transformed_body_start_line', 0),
                'transformed_body_end_line': self.metadata.get('transformed_body_end_line', 0),
                'fim_cursor_line': self.metadata.get('fim_cursor_line', 0),
                'fim_cursor_column': self.metadata.get('fim_cursor_column', 0),
                'fim_cursor_position': self.metadata.get('fim_cursor_position', 0)
            })
        
        return result
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'BenchmarkExample':
        """
        Создает экземпляр примера из словаря.
        
        Args:
            data: Словарь с данными примера
            
        Returns:
            Экземпляр BenchmarkExample
        """
        example = BenchmarkExample(
            original=data['original_code'],
            transformed=data['transformed_code'],
            metadata=data['metadata'],
            file_path=data.get('file_path', '')  # Добавляем получение file_path
        )
        
        # Восстанавливаем другие поля
        if 'context' in data:
            example.context = data['context']
        
        if 'id' in data:
            example.id = data['id']
        
        if 'created_at' in data:
            example.created_at = data['created_at']
        
        return example

    def get_task_description(self) -> str:
        """
        Возвращает описание задачи для примера.
        
        Returns:
            Строка с описанием задачи
        """
        # Если описание задачи уже есть в метаданных, используем его
        if 'task_description' in self.metadata:
            return self.metadata['task_description']
        
        # Иначе генерируем описание на основе типа трансформации
        transformation_type = self.metadata.get('type', 'unknown')
        
        if transformation_type == 'function_body_removal':
            function_name = self.metadata.get('function_name', 'unknown')
            return f"Заполните тело функции {function_name}, которое было удалено."
        
        elif transformation_type == 'function_call_removal':
            calls = self.metadata.get('replaced_calls', [])
            if calls:
                call_descriptions = ", ".join([call.get('function_name', 'unknown') for call in calls])
                return f"Восстановите вызовы функций, которые были удалены: {call_descriptions}."
            return "Восстановите удаленные вызовы функций."
        
        elif transformation_type == 'import_optimization':
            return "Восстановите импорты, которые были удалены или оптимизированы."
        
        # Для других типов трансформаций
        return "Восстановите код, который был трансформирован."
    
    def get_context_for_level(self, level: str = 'local') -> str:
        """
        Возвращает контекст определенного уровня.
        
        Args:
            level: Уровень контекста ('local', 'module', 'project')
            
        Returns:
            Строка с контекстом или пустая строка, если контекст не найден
        """
        return self.context.get(level, '')
    
    def _generate_id(self) -> str:
        """
        Генерирует уникальный идентификатор для примера.
        
        Returns:
            Строка с идентификатором
        """
        # Создаем хеш на основе оригинального кода и типа трансформации
        content = f"{self.original_code}_{self.metadata.get('type', 'unknown')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def __str__(self) -> str:
        """
        Возвращает строковое представление примера.
        
        Returns:
            Строка с информацией о примере
        """
        transformation_type = self.metadata.get('type', 'unknown')
        return f"BenchmarkExample(id={self.id}, type={transformation_type})"
