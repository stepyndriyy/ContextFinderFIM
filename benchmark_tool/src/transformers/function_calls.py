"""
Трансформатор для удаления вызовов функций.

Заменяет вызовы функций на их аргументы или другие выражения,
сохраняя семантику кода, где это возможно.
"""
import ast
import copy
import random
from typing import Dict, Any, List, Tuple, Optional, Set, Union

from benchmark_tool.src.transformers.base import CodeTransformer, TransformerRegistry


class FunctionCallRemover(CodeTransformer):
    """Трансформатор, удаляющий вызовы функций."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация трансформатора.
        
        Args:
            config: Конфигурация трансформатора
        """
        super().__init__(config)
        self.target_modules = config.get('target_modules', [])
        self.max_calls_removal = config.get('max_calls_removal', 1)
        self.replacement_strategy = config.get('replacement_strategy', 'first_arg')
        
    def can_transform(self, node: ast.AST) -> bool:
        """
        Проверяет, может ли вызов функции быть трансформирован.
        
        Критерии:
        - Узел должен быть вызовом функции (Call)
        - Вызов должен быть из целевого модуля, если указаны целевые модули
        - У вызова должен быть хотя бы один аргумент для замены
        
        Args:
            node: Узел AST для проверки
            
        Returns:
            True, если вызов может быть трансформирован
        """
        if not isinstance(node, ast.Call):
            return False
        
        # Если у вызова нет аргументов и мы используем стратегию с аргументами,
        # то не можем трансформировать
        if self.replacement_strategy == 'first_arg' and not node.args:
            return False
        
        # Если целевые модули не указаны, можем трансформировать любой вызов
        if not self.target_modules:
            return True
        
        # Проверяем, принадлежит ли вызов к целевому модулю
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            # Случай module.function()
            return node.func.value.id in self.target_modules
        
        return False
    
    def remove_function_call(self, node: ast.Call) -> ast.AST:
        """
        Заменяет вызов функции на альтернативное выражение.
        
        Стратегии замены:
        - first_arg: возвращает первый аргумент вызова
        - literal: заменяет на литерал подходящего типа
        - none: заменяет на None
        
        Args:
            node: Узел вызова функции
            
        Returns:
            Новый узел AST для замены вызова
        """
        if self.replacement_strategy == 'first_arg' and node.args:
            return node.args[0]
        elif self.replacement_strategy == 'literal':
            # Определяем, какой литерал использовать на основе контекста
            return ast.Constant(value=0)  # По умолчанию используем число
        elif self.replacement_strategy == 'none':
            return ast.Constant(value=None)
        else:
            # Если не можем применить стратегию, оставляем вызов без изменений
            return node
    
    def analyze_call_impact(self, node: ast.Call) -> Dict[str, Any]:
        """
        Анализирует влияние удаления вызова функции.
        
        Args:
            node: Узел вызова функции
            
        Returns:
            Словарь с информацией о влиянии удаления
        """
        impact = {
            "function_name": None,
            "has_args": len(node.args) > 0,
            "has_keywords": len(node.keywords) > 0,
            "is_attribute_call": isinstance(node.func, ast.Attribute)
        }
        
        # Определяем имя функции
        if isinstance(node.func, ast.Name):
            impact["function_name"] = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                impact["function_name"] = f"{node.func.value.id}.{node.func.attr}"
            else:
                impact["function_name"] = f"?.{node.func.attr}"
        
        return impact
    
    class CallTransformer(ast.NodeTransformer):
        """Внутренний класс для трансформации вызовов функций."""
        
        def __init__(self, remover, max_replacements: int):
            self.remover = remover
            self.max_replacements = max_replacements
            self.replacements_made = 0
            self.replaced_nodes = []
        
        def visit_Call(self, node: ast.Call):
            # Если достигли максимального числа замен, прекращаем трансформацию
            if self.replacements_made >= self.max_replacements:
                return self.generic_visit(node)
            
            # Проверяем, можно ли трансформировать вызов
            if self.remover.can_transform(node) and self.remover.should_transform():
                # Анализируем влияние замены
                impact = self.remover.analyze_call_impact(node)
                
                # Заменяем вызов
                replacement = self.remover.remove_function_call(node)
                
                # Увеличиваем счетчик замен
                self.replacements_made += 1
                
                # Сохраняем информацию о замененном узле
                self.replaced_nodes.append({
                    "original": node,
                    "replacement": replacement,
                    "impact": impact
                })
                
                return replacement
            
            return self.generic_visit(node)
    
    def transform(self, ast_tree: ast.Module) -> Tuple[ast.Module, Dict[str, Any]]:
        """
        Применяет трансформацию к AST дереву.
        
        Args:
            ast_tree: AST дерево для трансформации
            
        Returns:
            Кортеж из трансформированного AST и метаданных
        """
        # Создаем копию дерева
        new_tree = copy.deepcopy(ast_tree)
        
        # Создаем трансформер
        transformer = self.CallTransformer(self, self.max_calls_removal)
        
        # Применяем трансформацию
        transformed_tree = transformer.visit(new_tree)
        transformed_tree = ast.fix_missing_locations(transformed_tree)
        
        # Если не было замен, возвращаем исходное дерево
        if not transformer.replaced_nodes:
            return new_tree, {"success": False, "reason": "No suitable function calls found"}
        
        # Собираем метаданные о трансформации
        self.metadata = {
            "success": True,
            "replacements_made": transformer.replacements_made,
            "replaced_calls": [
                {
                    "function_name": node["impact"]["function_name"],
                    "line_number": node["original"].lineno if hasattr(node["original"], "lineno") else None,
                    "replacement_type": type(node["replacement"]).__name__
                }
                for node in transformer.replaced_nodes
            ],
            "type": "function_call_removal"
        }
        
        return transformed_tree, self.metadata


# Регистрируем трансформатор
TransformerRegistry.register("function_call", FunctionCallRemover)
