"""
Базовый модуль для трансформаций кода.
Определяет абстрактные классы и интерфейсы для всех трансформаторов.
"""
import ast
from abc import ABC, abstractmethod
import random
import astor
from typing import Dict, Any, List, Optional, Set, Tuple, Union

from utils.logging_utils import setup_logger, log_transformation
import ast_parser

# Настраиваем логгер
logger = setup_logger("code_transformer")


class CodeTransformer(ABC):
    """
    Абстрактный базовый класс для всех трансформаций кода.
    
    Все конкретные трансформеры должны наследоваться от этого класса
    и реализовывать абстрактные методы.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация трансформера.
        
        Args:
            config: Конфигурация трансформера из файла настроек
        """
        self.config = config
        self.probability = config.get('probability', 0.5)
        self.metadata = {}  # Метаданные о последней трансформации
    
    @abstractmethod
    def transform(self, ast_tree: ast.Module) -> Tuple[ast.Module, Dict[str, Any]]:
        """
        Применяет трансформацию к AST дереву.
        
        Args:
            ast_tree: AST дерево для трансформации
            
        Returns:
            Кортеж из трансформированного AST и метаданных
        """
        pass
    
    @abstractmethod
    def can_transform(self, node: ast.AST) -> bool:
        """
        Проверяет, может ли узел быть трансформирован.
        
        Args:
            node: Узел AST для проверки
            
        Returns:
            True, если узел может быть трансформирован, иначе False
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Возвращает метаданные о последней трансформации.
        
        Returns:
            Словарь с метаданными
        """
        return self.metadata
    
    def should_transform(self) -> bool:
        """
        Определяет, должна ли трансформация быть применена,
        на основе вероятности из конфигурации.
        
        Returns:
            True, если трансформация должна быть применена, иначе False
        """
        return random.random() < self.probability
    
    def apply_transformation(self, original_code: str, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Applies transformation to code.
        
        Args:
            original_code: Original source code
            file_path: Path to file (for logging)
            
        Returns:
            Tuple of transformed code and metadata
        """
        try:
            # Parse code to AST
            ast_tree = ast.parse(original_code)
            
            # Apply transform to get metadata and initial tree
            new_tree, metadata = self.transform(ast_tree)
            
            # If no suitable function was found
            if not metadata.get("success", True):
                return original_code, metadata
            
            # Extract the function to transform
            function_to_transform = metadata.get("function_to_transform")
            if not function_to_transform:
                return original_code, {"success": False, "reason": "No function to transform"}
            
            # Make sure this method exists on the transformer
            if not hasattr(self, 'remove_function_body'):
                return original_code, {"success": False, "reason": "Transformer doesn't implement remove_function_body"}
            
            # Apply direct source transformation
            transformed_code, metadata = self.remove_function_body(function_to_transform, original_code)
            
            # Log the transformation
            if metadata.get("success", False):
                log_transformation(original_code, transformed_code, self.__class__.__name__, metadata)
                
            return transformed_code, metadata
            
        except Exception as e:
            logger.error(f"Error when transforming {file_path}: {e}")
            return original_code, {"error": str(e), "success": False}
    

class TransformerRegistry:
    """
    Реестр всех доступных трансформеров.
    Используется для получения экземпляров трансформеров по имени.
    """
    _transformers = {}
    
    @classmethod
    def register(cls, name: str, transformer_class):
        """
        Регистрирует класс трансформера.
        
        Args:
            name: Имя трансформера
            transformer_class: Класс трансформера
        """
        cls._transformers[name] = transformer_class
    
    @classmethod
    def get_transformer(cls, name: str, config: Dict[str, Any]) -> Optional[CodeTransformer]:
        """
        Создает экземпляр трансформера по имени.
        
        Args:
            name: Имя трансформера
            config: Конфигурация для трансформера
            
        Returns:
            Экземпляр трансформера или None, если трансформер не найден
        """
        transformer_class = cls._transformers.get(name)
        if transformer_class:
            return transformer_class(config)
        return None
    
    @classmethod
    def list_transformers(cls) -> List[str]:
        """
        Возвращает список названий всех зарегистрированных трансформеров.
        
        Returns:
            Список имен трансформеров
        """
        return list(cls._transformers.keys())
