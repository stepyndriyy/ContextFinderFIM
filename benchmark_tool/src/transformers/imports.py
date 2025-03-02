"""
Модуль для работы с импортами при трансформациях кода.

Позволяет правильно обрабатывать импорты при трансформациях,
сохраняя необходимые импорты даже после изменения кода.
"""
import ast
import copy
from typing import Dict, Any, List, Tuple, Set, Optional

from benchmark_tool.src.transformers.base import CodeTransformer, TransformerRegistry
import ast_parser


class ImportPreserver:
    """
    Класс для работы с импортами при трансформациях.
    
    Отвечает за анализ и сохранение необходимых импортов после 
    трансформации кода.
    """
    
    @classmethod
    def collect_required_imports(cls, ast_tree: ast.Module, transformed_code: str) -> Set[str]:
        """
        Определяет необходимые импорты на основе трансформированного кода.
        
        Анализирует AST и находит все имена, которые используются в коде,
        затем сопоставляет их с импортами для определения необходимых.
        
        Args:
            ast_tree: Исходное AST дерево с импортами
            transformed_code: Трансформированный код
            
        Returns:
            Множество имен импортов, которые необходимо сохранить
        """
        # Получаем все импорты из исходного AST
        imports, from_imports = ast_parser.find_imports(ast_tree)
        
        # Парсим трансформированный код для анализа
        try:
            transformed_tree = ast.parse(transformed_code)
        except SyntaxError:
            # Если трансформированный код имеет синтаксические ошибки,
            # лучше сохранить все импорты для безопасности
            return cls._get_all_imported_names(imports, from_imports)
        
        # Находим все имена, используемые в трансформированном коде
        used_names = cls._find_used_names(transformed_tree)
        
        # Находим все импортированные имена
        imported_names = cls._get_all_imported_names(imports, from_imports)
        
        # Определяем, какие импорты нужно сохранить
        required_imports = set()
        
        # Проверяем прямые импорты (import x, y)
        for imp in imports:
            for name in imp.names:
                # Добавляем имя, если оно используется непосредственно
                if name.name in used_names:
                    required_imports.add(name.name)
                # Или если используется с псевдонимом
                elif name.asname and name.asname in used_names:
                    required_imports.add(name.name)
                # Или если используются атрибуты импортированного модуля
                else:
                    for used_name in used_names:
                        if isinstance(used_name, str) and used_name.startswith(name.name + "."):
                            required_imports.add(name.name)
                            break
        
        # Проверяем импорты from (from x import y, z)
        for imp in from_imports:
            module_name = imp.module
            for name in imp.names:
                actual_name = name.asname if name.asname else name.name
                if actual_name in used_names or name.name in used_names:
                    # Для импортов 'from' сохраняем полное имя модуля + импортируемое имя
                    required_imports.add(f"{module_name}.{name.name}")
        
        return required_imports
    
    @staticmethod
    def _get_all_imported_names(imports: List[ast.Import], from_imports: List[ast.ImportFrom]) -> Set[str]:
        """
        Получает все имена, импортированные в модуле.
        
        Args:
            imports: Список импортов (import x, y)
            from_imports: Список from-импортов (from x import y, z)
            
        Returns:
            Множество всех импортированных имен
        """
        imported_names = set()
        
        # Добавляем имена из прямых импортов
        for imp in imports:
            for name in imp.names:
                if name.asname:
                    imported_names.add(name.asname)
                else:
                    imported_names.add(name.name)
        
        # Добавляем имена из from-импортов
        for imp in from_imports:
            for name in imp.names:
                if name.asname:
                    imported_names.add(name.asname)
                else:
                    imported_names.add(name.name)
        
        return imported_names
    
    @staticmethod
    def _find_used_names(ast_tree: ast.Module) -> Set[str]:
        """
        Находит все имена, используемые в AST дереве.
        
        Args:
            ast_tree: AST дерево для анализа
            
        Returns:
            Множество используемых имен
        """
        class NameVisitor(ast.NodeVisitor):
            def __init__(self):
                self.names = set()
                
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    self.names.add(node.id)
                self.generic_visit(node)
                
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    # Для атрибутов типа module.attr добавляем полное имя
                    self.names.add(f"{node.value.id}.{node.attr}")
                self.generic_visit(node)
        
        visitor = NameVisitor()
        visitor.visit(ast_tree)
        return visitor.names
    
    @classmethod
    def ensure_imports_preserved(cls, original_tree: ast.Module, transformed_tree: ast.Module) -> ast.Module:
        """
        Сохраняет необходимые импорты в трансформированном дереве.
        
        Args:
            original_tree: Исходное AST дерево с импортами
            transformed_tree: Трансформированное AST дерево
            
        Returns:
            AST дерево с сохраненными импортами
        """
        # Получаем все импорты из исходного дерева
        original_imports, original_from_imports = ast_parser.find_imports(original_tree)
        
        # Получаем все импорты из трансформированного дерева
        transformed_imports, transformed_from_imports = ast_parser.find_imports(transformed_tree)
        
        # Создаем копию трансформированного дерева
        result_tree = copy.deepcopy(transformed_tree)
        
        # Собираем имена, используемые в трансформированном дереве
        used_names = cls._find_used_names(transformed_tree)
        
        # Импорты, которые нужно добавить
        imports_to_add = []
        from_imports_to_add = []
        
        # Проверяем обычные импорты (import x, y)
        for imp in original_imports:
            # Проверяем, есть ли такой импорт уже в трансформированном дереве
            is_already_imported = False
            for transformed_imp in transformed_imports:
                # Сравниваем имена импортов
                if all(any(n1.name == n2.name for n2 in transformed_imp.names) for n1 in imp.names):
                    is_already_imported = True
                    break
            
            # Если импорта нет и его имена используются, добавляем его
            if not is_already_imported and any(name.name in used_names or 
                                             (name.asname and name.asname in used_names) for name in imp.names):
                imports_to_add.append(imp)
        
        # Проверяем from-импорты (from x import y, z)
        for imp in original_from_imports:
            # Проверяем, есть ли такой импорт уже в трансформированном дереве
            is_already_imported = False
            for transformed_imp in transformed_from_imports:
                if imp.module == transformed_imp.module:
                    # Сравниваем имена импортов
                    if all(any(n1.name == n2.name for n2 in transformed_imp.names) for n1 in imp.names):
                        is_already_imported = True
                        break
            
            # Если импорта нет и его имена используются, добавляем его
            used_from_import = False
            for name in imp.names:
                actual_name = name.asname if name.asname else name.name
                if actual_name in used_names:
                    used_from_import = True
                    break
            
            if not is_already_imported and used_from_import:
                from_imports_to_add.append(imp)
        
        # Добавляем необходимые импорты в начало дерева
        # Сначала добавляем обычные импорты
        result_tree.body = imports_to_add + result_tree.body
        
        # Затем добавляем from-импорты
        # Их нужно вставить после обычных импортов, но перед остальным кодом
        if from_imports_to_add:
            insert_position = len(imports_to_add)
            for imp in from_imports_to_add:
                result_tree.body.insert(insert_position, imp)
                insert_position += 1
        
        # Исправляем линии AST после вставки новых узлов
        ast.fix_missing_locations(result_tree)
        
        return result_tree


class ImportOptimizer(CodeTransformer):
    """
    Трансформатор для оптимизации импортов.
    
    Удаляет неиспользуемые импорты и объединяет повторяющиеся.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация трансформатора.
        
        Args:
            config: Конфигурация трансформатора
        """
        super().__init__(config)
        self.remove_unused = config.get('remove_unused', True)
        self.combine_imports = config.get('combine_imports', True)
    
    def can_transform(self, node: ast.AST) -> bool:
        """
        Проверяет, может ли узел быть трансформирован.
        
        Args:
            node: Узел AST для проверки
            
        Returns:
            True, если узел может быть трансформирован
        """
        return isinstance(node, (ast.Import, ast.ImportFrom))
    
    def transform(self, ast_tree: ast.Module) -> Tuple[ast.Module, Dict[str, Any]]:
        """
        Оптимизирует импорты в AST дереве.
        
        Args:
            ast_tree: AST дерево для трансформации
            
        Returns:
            Кортеж из трансформированного AST и метаданных
        """
        # Создаем копию дерева
        new_tree = copy.deepcopy(ast_tree)
        
        # Находим используемые имена в коде
        used_names = ImportPreserver._find_used_names(new_tree)
        
        # Получаем импорты
        imports, from_imports = ast_parser.find_imports(new_tree)
        
        # Метаданные трансформации
        self.metadata = {
            "success": False,
            "removed_imports": [],
            "combined_imports": [],
            "type": "import_optimization"
        }
        
        if self.remove_unused:
            new_tree, removed = self._remove_unused_imports(new_tree, used_names)
            if removed:
                self.metadata["success"] = True
                self.metadata["removed_imports"] = removed
        
        if self.combine_imports:
            new_tree, combined = self._combine_duplicate_imports(new_tree)
            if combined:
                self.metadata["success"] = True
                self.metadata["combined_imports"] = combined
        
        return new_tree, self.metadata
    
    def _remove_unused_imports(self, ast_tree: ast.Module, used_names: Set[str]) -> Tuple[ast.Module, List[str]]:
        """
        Удаляет неиспользуемые импорты из AST дерева.
        
        Args:
            ast_tree: AST дерево
            used_names: Множество используемых имен
            
        Returns:
            Кортеж из AST дерева с удаленными импортами и списка удаленных импортов
        """
        removed_imports = []
        new_body = []
        
        for node in ast_tree.body:
            if isinstance(node, ast.Import):
                # Проверяем каждое имя в импорте
                needed_names = []
                for name in node.names:
                    actual_name = name.asname if name.asname else name.name
                    
                    # Проверяем, используется ли импорт
                    is_used = actual_name in used_names
                    
                    # Также проверяем использование атрибутов импорта
                    if not is_used:
                        for used_name in used_names:
                            if isinstance(used_name, str) and used_name.startswith(actual_name + "."):
                                is_used = True
                                break
                    
                    if is_used:
                        needed_names.append(name)
                    else:
                        removed_imports.append(name.name)
                
                # Если остались какие-то имена, сохраняем импорт
                if needed_names:
                    new_import = ast.Import(names=needed_names)
                    ast.copy_location(new_import, node)
                    new_body.append(new_import)

            elif isinstance(node, ast.ImportFrom):
                # Проверяем каждое имя в from-импорте
                needed_names = []
                module_name = node.module
                
                for name in node.names:
                    actual_name = name.asname if name.asname else name.name
                    
                    # Проверяем, используется ли имя
                    if actual_name in used_names:
                        needed_names.append(name)
                    else:
                        removed_imports.append(f"{module_name}.{name.name}")
                
                # Если остались какие-то имена, сохраняем импорт
                if needed_names:
                    new_import = ast.ImportFrom(
                        module=module_name,
                        names=needed_names,
                        level=node.level
                    )
                    ast.copy_location(new_import, node)
                    new_body.append(new_import)
            
            else:
                # Не импорт - сохраняем как есть
                new_body.append(node)
        
        # Создаем новое дерево с обновленным телом
        result_tree = ast.Module(body=new_body, type_ignores=[])
        ast.fix_missing_locations(result_tree)
        
        return result_tree, removed_imports
    
    def _combine_duplicate_imports(self, ast_tree: ast.Module) -> Tuple[ast.Module, List[str]]:
        """
        Объединяет повторяющиеся импорты в AST дереве.
        
        Args:
            ast_tree: AST дерево
            
        Returns:
            Кортеж из AST дерева с объединенными импортами и списка объединенных импортов
        """
        combined_imports = []
        
        # Словари для отслеживания импортов
        import_dict = {}  # {module: [names]}
        from_import_dict = {}  # {(module, level): [names]}
        
        # Проходим по всем импортам и группируем их
        imports_to_remove = []
        for i, node in enumerate(ast_tree.body):
            if isinstance(node, ast.Import):
                for name in node.names:
                    module = name.name
                    if module not in import_dict:
                        import_dict[module] = []
                    import_dict[module].append(name)
                
                # Помечаем для удаления
                imports_to_remove.append(i)
                
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                level = node.level
                key = (module, level)
                
                if key not in from_import_dict:
                    from_import_dict[key] = []
                
                # Добавляем все имена из импорта
                for name in node.names:
                    # Проверяем, нет ли уже такого имени с другим псевдонимом
                    if not any(existing.name == name.name for existing in from_import_dict[key]):
                        from_import_dict[key].append(name)
                
                # Помечаем для удаления
                imports_to_remove.append(i)
        
        # Создаем новые импорты на основе словарей
        new_imports = []
        
        # Обычные импорты
        for module, names in import_dict.items():
            # Если есть дубликаты, записываем в метаданные
            if len(names) > 1:
                combined_imports.append(f"import {module}")
            
            # Создаем новый импорт
            import_node = ast.Import(names=names)
            ast.fix_missing_locations(import_node)
            new_imports.append(import_node)
        
        # From-импорты
        for (module, level), names in from_import_dict.items():
            # Если есть дубликаты, записываем в метаданные
            if len(names) > 1:
                imports_str = ", ".join(name.name for name in names)
                combined_imports.append(f"from {module} import {imports_str}")
            
            # Создаем новый импорт
            from_import_node = ast.ImportFrom(
                module=module,
                names=names,
                level=level
            )
            ast.fix_missing_locations(from_import_node)
            new_imports.append(from_import_node)
        
        # Создаем новое тело AST, вставляя объединенные импорты в начало
        new_body = []
        
        # Добавляем все новые импорты
        new_body.extend(new_imports)
        
        # Добавляем остальной код (кроме старых импортов)
        for i, node in enumerate(ast_tree.body):
            if i not in imports_to_remove:
                new_body.append(node)
        
        # Создаем новое AST дерево
        result_tree = ast.Module(body=new_body, type_ignores=[])
        ast.fix_missing_locations(result_tree)
        
        return result_tree, combined_imports


# Регистрируем трансформатор
TransformerRegistry.register("import_optimizer", ImportOptimizer)
