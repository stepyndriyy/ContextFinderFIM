"""
Модуль для парсинга и анализа Python-кода с использованием AST.
"""
import ast
import os
import sys
import astor
from typing import List, Dict, Any, Optional, Tuple, Set, Union

from utils.logging_utils import setup_logger
from utils.file_utils import read_file

# Настройка логгера
logger = setup_logger("ast_parser")

class FunctionVisitor(ast.NodeVisitor):
    """Визитор для поиска функций и методов в AST."""
    
    def __init__(self):
        self.functions = []
        self.methods = []
        self.current_class = None
    
    def visit_ClassDef(self, node):
        """Посещение определения класса."""
        old_class = self.current_class
        self.current_class = node
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node):
        """Посещение определения функции."""
        if self.current_class:
            self.methods.append(node)
        else:
            self.functions.append(node)
        self.generic_visit(node)


class ImportVisitor(ast.NodeVisitor):
    """Визитор для поиска импортов в AST."""
    
    def __init__(self):
        self.imports = []
        self.from_imports = []
    
    def visit_Import(self, node):
        """Посещение простого импорта: import x, y."""
        self.imports.append(node)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Посещение from-импорта: from x import y, z."""
        self.from_imports.append(node)
        self.generic_visit(node)


class FunctionCallVisitor(ast.NodeVisitor):
    """Визитор для поиска вызовов функций в AST."""
    
    def __init__(self):
        self.calls = []
    
    def visit_Call(self, node):
        """Посещение вызова функции."""
        self.calls.append(node)
        self.generic_visit(node)


class NameVisitor(ast.NodeVisitor):
    """Визитор для поиска имен (переменных, функций) в AST."""
    
    def __init__(self):
        self.names = set()
    
    def visit_Name(self, node):
        """Посещение имени (переменной, функции и т.д.)."""
        if isinstance(node.ctx, ast.Load):  # Только использование, не присваивание
            self.names.add(node.id)
        self.generic_visit(node)


def parse_file(file_path: str) -> Optional[ast.Module]:
    """
    Парсинг файла в AST.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        AST дерево или None в случае ошибки
    """
    content = read_file(file_path)
    if not content:
        logger.error(f"Не удалось прочитать файл: {file_path}")
        return None
    
    try:
        tree = ast.parse(content, filename=file_path)
        return tree
    except SyntaxError as e:
        logger.error(f"Ошибка синтаксиса при парсинге {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при парсинге {file_path}: {e}")
        return None


def find_functions(ast_tree: ast.Module) -> Tuple[List[ast.FunctionDef], List[ast.FunctionDef]]:
    """
    Поиск всех функций и методов в AST.
    
    Args:
        ast_tree: AST дерево
        
    Returns:
        Кортеж из списка функций и списка методов
    """
    visitor = FunctionVisitor()
    visitor.visit(ast_tree)
    return visitor.functions, visitor.methods


def find_imports(ast_tree: ast.Module) -> Tuple[List[ast.Import], List[ast.ImportFrom]]:
    """
    Извлечение всех импортов из AST.
    
    Args:
        ast_tree: AST дерево
        
    Returns:
        Кортеж из списка импортов и списка from-импортов
    """
    visitor = ImportVisitor()
    visitor.visit(ast_tree)
    return visitor.imports, visitor.from_imports


def find_function_calls(ast_tree: ast.Module) -> List[ast.Call]:
    """
    Идентификация вызовов функций в AST.
    
    Args:
        ast_tree: AST дерево
        
    Returns:
        Список узлов вызова функций
    """
    visitor = FunctionCallVisitor()
    visitor.visit(ast_tree)
    return visitor.calls


def find_function_calls_in_node(node: ast.AST) -> List[ast.Call]:
    """
    Идентификация вызовов функций в конкретном узле AST.
    
    Args:
        node: Узел AST
        
    Returns:
        Список узлов вызова функций
    """
    visitor = FunctionCallVisitor()
    visitor.visit(node)
    return visitor.calls


def get_function_dependencies(function_node: ast.FunctionDef) -> Set[str]:
    """
    Определение зависимостей функции (используемые имена).
    
    Args:
        function_node: Узел функции
        
    Returns:
        Множество используемых имен
    """
    visitor = NameVisitor()
    visitor.visit(function_node)
    return visitor.names


def get_function_source(function_node: ast.FunctionDef) -> str:
    """
    Получение исходного кода функции из AST.
    
    Args:
        function_node: Узел функции
        
    Returns:
        Строка с исходным кодом функции
    """
    return astor.to_source(function_node)


def extract_context(
    ast_tree: ast.Module,
    node: ast.AST,
    context_level: str = "local"
) -> Dict[str, Any]:
    """
    Извлечение контекста нужного уровня для узла AST.
    
    Args:
        ast_tree: Полное AST дерево
        node: Узел, для которого извлекается контекст
        context_level: Уровень контекста ('none', 'minimal', 'local', 'extended')
        
    Returns:
        Словарь с информацией о контексте
    """
    context = {
        "level": context_level,
        "imports": [],
        "related_functions": [],
        "related_classes": []
    }
    
    if context_level == "none":
        return context
    
    # Для минимального контекста добавляем только импорты
    if context_level in ["minimal", "local", "extended"]:
        imports, from_imports = find_imports(ast_tree)
        
        for import_node in imports:
            for name in import_node.names:
                context["imports"].append({
                    "type": "import",
                    "module": name.name,
                    "asname": name.asname
                })
        
        for from_import in from_imports:
            for name in from_import.names:
                context["imports"].append({
                    "type": "from_import",
                    "module": from_import.module,
                    "name": name.name,
                    "asname": name.asname
                })
    
    # Для локального контекста добавляем функции и классы из того же файла
    if context_level in ["local", "extended"]:
        functions, methods = find_functions(ast_tree)
        
        for func in functions:
            # Пропускаем сам узел, если это функция
            if isinstance(node, ast.FunctionDef) and func.name == node.name:
                continue
            
            context["related_functions"].append({
                "name": func.name,
                "source": get_function_source(func),
                "dependencies": list(get_function_dependencies(func))
            })
        
        # Также добавляем определения классов
        for class_node in ast.walk(ast_tree):
            if isinstance(class_node, ast.ClassDef):
                class_info = {
                    "name": class_node.name,
                    "methods": []
                }
                
                for method in class_node.body:
                    if isinstance(method, ast.FunctionDef):
                        # Пропускаем сам узел, если это метод
                        if isinstance(node, ast.FunctionDef) and method.name == node.name:
                            continue
                        
                        class_info["methods"].append({
                            "name": method.name,
                            "source": get_function_source(method),
                            "dependencies": list(get_function_dependencies(method))
                        })
                
                context["related_classes"].append(class_info)
    
    # Расширенный контекст будет дополнен в code_processor.py, когда будет
    # анализироваться информация из других файлов
    
    return context


def get_node_by_name(ast_tree: ast.Module, name: str) -> Optional[ast.AST]:
    """
    Поиск узла AST по его имени.
    
    Args:
        ast_tree: AST дерево
        name: Имя искомого узла (функции, класса)
        
    Returns:
        Найденный узел или None
    """
    for node in ast.walk(ast_tree):
        if (isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                and hasattr(node, 'name') and node.name == name):
            return node
    return None


def node_to_source(node: ast.AST) -> str:
    """
    Преобразование узла AST в исходный код.
    
    Args:
        node: Узел AST
        
    Returns:
        Строка с исходным кодом
    """
    return astor.to_source(node)
