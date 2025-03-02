import os
import ast
import sys
import builtins
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple, Any, Union


class ImportInfo:
    """Класс для хранения информации об импорте"""
    def __init__(self, module_path: Path, import_type: str, names: List[str] = None):
        self.module_path = module_path  # Путь к модулю
        self.import_type = import_type  # 'import' или 'from'
        self.names = names or []  # Список импортируемых имен (для from import)
        self.used_names = set()  # Имена, которые реально используются в коде


class CodeElement:
    """Класс для представления элемента кода (функция, класс, константа)"""
    def __init__(self, name: str, element_type: str, source_code: str, deps: List[str] = None):
        self.name = name  # Имя элемента
        self.element_type = element_type  # 'function', 'class', 'constant' и т.д.
        self.source_code = source_code  # Исходный код элемента
        self.deps = deps or []  # Зависимости элемента (какие имена использует)


class CodeContextCollector:
    """
    Улучшенный класс для сбора контекста кода из локальных импортов.
    
    Анализирует Python файлы, определяет локальные импорты и анализирует
    какие именно функции/классы/константы используются, собирая только их.
    """
    
    def __init__(self, project_root: Optional[str] = None, max_file_size: int = 1_000_000):
        """
        Инициализирует сборщик контекста.
        
        Args:
            project_root: Корневая директория проекта. Если None, определяется автоматически.
            max_file_size: Максимальный размер файла для включения в контекст (в байтах)
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.max_file_size = max_file_size
        
        # Кэш для хранения содержимого и AST файлов
        self.file_cache: Dict[str, str] = {}
        self.ast_cache: Dict[str, ast.Module] = {}
        
        # Словарь элементов кода: {имя_модуля: {имя_элемента: CodeElement}}
        self.code_elements: Dict[str, Dict[str, CodeElement]] = {}
        
        # Словарь импортов: {имя_импорта: ImportInfo}
        self.imports: Dict[str, ImportInfo] = {}
        
        # Отслеживание обработанных файлов для предотвращения циклических зависимостей
        self.processed_files: Set[str] = set()
        
        # Стандартные библиотеки Python и популярные внешние пакеты, которые нужно игнорировать
        self.std_libs = set(sys.stdlib_module_names)
        self.builtin_names = set(dir(builtins))
        self.external_libs = {
            'numpy', 'pandas', 'matplotlib', 'seaborn', 'sklearn', 'scipy', 
            'torch', 'tensorflow', 'keras', 'transformers', 'nltk', 'spacy',
            'cv2', 'PIL', 'requests', 'bs4', 'sqlalchemy', 'django', 'flask',
            'fastapi', 'pytest', 'unittest', 'json', 're', 'os', 'sys', 'time',
            'datetime', 'collections', 'itertools', 'functools', 'typing',
            'pathlib', 'argparse', 'logging'
        }
    
    def collect_context(self, file_path: str) -> Dict[str, Dict[str, CodeElement]]:
        """
        Собирает контекст из указанного файла и всех его локальных зависимостей.
        
        Args:
            file_path: Путь к файлу, с которого начинается сбор контекста
            
        Returns:
            Словарь элементов кода, сгруппированных по модулям
        """
        self.processed_files.clear()
        self.file_cache.clear()
        self.ast_cache.clear()
        self.code_elements.clear()
        self.imports.clear()
        
        abs_path = self._resolve_path(file_path)
        self._process_file(abs_path)
        
        # Выполняем второй проход для анализа используемых элементов
        self._analyze_usage(abs_path)
        
        return self.code_elements
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        Преобразует относительный или абсолютный путь в абсолютный.
        
        Args:
            file_path: Путь к файлу (относительный или абсолютный)
            
        Returns:
            Абсолютный путь к файлу
        """
        path = Path(file_path)
        if path.is_absolute():
            return path
        
        # First check if the file exists relative to the current working directory
        if Path(file_path).exists():
            return Path(file_path).resolve()
        
        # Then check if the file exists relative to the project root
        if (self.project_root / file_path).exists():
            return (self.project_root / file_path).resolve()
        
        # As a fallback, try to intelligently handle path components
        # Split the file_path and remove any parts that might overlap with project_root
        path_parts = list(path.parts)
        for part in self.project_root.parts:
            if path_parts and path_parts[0] == part:
                path_parts.pop(0)
            else:
                break
        
        return (self.project_root / Path(*path_parts)).resolve()
    
    def _process_file(self, file_path: Path) -> None:
        """
        Обрабатывает файл: читает его содержимое, анализирует импорты,
        извлекает определения функций/классов/констант и рекурсивно 
        обрабатывает все локальные зависимости.
        
        Args:
            file_path: Абсолютный путь к файлу для обработки
        """
        # Пропускаем уже обработанные файлы для предотвращения циклов
        str_path = str(file_path)
        if str_path in self.processed_files:
            return
        
        # Отмечаем файл как обработанный
        self.processed_files.add(str_path)
        
        # Проверяем, что файл существует и имеет расширение .py
        if not file_path.exists() or file_path.suffix != '.py':
            return
        
        # Проверяем размер файла
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            print(f"Пропуск слишком большого файла: {file_path} ({file_size} байт)")
            return
        
        try:
            # Читаем содержимое файла
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Сохраняем содержимое в кэше
            self.file_cache[str_path] = content
            
            # Парсим AST
            module_ast = ast.parse(content, filename=str(file_path))
            self.ast_cache[str_path] = module_ast
            
            # Извлекаем элементы кода (функции, классы, константы)
            self._extract_code_elements(str_path, module_ast)
            
            # Анализируем импорты
            imports = self._extract_imports(module_ast, file_path)
            
            # Сохраняем информацию об импортах для текущего файла
            for imp in imports:
                module_name = self._get_module_name(imp.module_path)
                if module_name not in self.imports:
                    self.imports[module_name] = imp
            
            # Обрабатываем каждый импорт
            for imp in imports:
                self._process_file(imp.module_path)
                
        except SyntaxError as e:
            print(f"Ошибка синтаксического анализа файла {file_path}: {e}")
        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {e}")
    
    def _get_module_name(self, module_path: Path) -> str:
        """Получает имя модуля из пути к файлу"""
        module_name = module_path.stem
        # Для пакетов (__init__.py) используем имя директории
        if module_name == "__init__":
            module_name = module_path.parent.name
        return module_name
    
    def _extract_code_elements(self, file_path: str, module_ast: ast.Module) -> None:
        """
        Извлекает элементы кода (функции, классы, константы) из AST.
        
        Args:
            file_path: Путь к файлу
            module_ast: AST модуля
        """
        module_name = self._get_module_name(Path(file_path))
        if module_name not in self.code_elements:
            self.code_elements[module_name] = {}
        
        # Анализ верхнего уровня AST
        for node in module_ast.body:
            # Функции
            if isinstance(node, ast.FunctionDef):
                source_code = self._get_source_code(file_path, node)
                deps = self._extract_dependencies(node)
                element = CodeElement(
                    name=node.name,
                    element_type='function',
                    source_code=source_code,
                    deps=deps
                )
                self.code_elements[module_name][node.name] = element
            
            # Классы
            elif isinstance(node, ast.ClassDef):
                source_code = self._get_source_code(file_path, node)
                deps = self._extract_dependencies(node)
                element = CodeElement(
                    name=node.name,
                    element_type='class',
                    source_code=source_code,
                    deps=deps
                )
                self.code_elements[module_name][node.name] = element
            
            # Константы и переменные верхнего уровня
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        source_code = self._get_source_code(file_path, node)
                        deps = self._extract_dependencies(node)
                        element = CodeElement(
                            name=target.id,
                            element_type='constant',
                            source_code=source_code,
                            deps=deps
                        )
                        self.code_elements[module_name][target.id] = element
    
    def _get_source_code(self, file_path: str, node: ast.AST) -> str:
        """Получает исходный код для узла AST"""
        content = self.file_cache[file_path]
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', start_line) if hasattr(node, 'end_lineno') else start_line
        
        # Если нет end_lineno (для старых версий Python), придется искать вручную
        if not hasattr(node, 'end_lineno'):
            lines = content.splitlines()
            current_depth = 0
            for i, line in enumerate(lines[start_line:], start=start_line):
                # Упрощенная эвристика для определения конца блока
                if ':' in line:
                    current_depth += 1
                if (line.startswith(' ' * 4 * (current_depth - 1)) and 
                    not line.strip().startswith(' ')):
                    end_line = i - 1
                    break
                if i == len(lines) - 1:
                    end_line = i
        
        lines = content.splitlines()[start_line:end_line+1]
        return '\n'.join(lines)
    
    def _extract_dependencies(self, node: ast.AST) -> List[str]:
        """
        Извлекает имена, от которых зависит данный узел AST.
        Например, для функции извлечет все переменные, функции, классы,
        которые она использует.
        """
        deps = []
        
        class DependencyVisitor(ast.NodeVisitor):
            def __init__(self, collector):
                self.collector = collector
                self.names = []
            
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id not in self.collector.builtin_names:
                    self.names.append(node.id)
                self.generic_visit(node)
            
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    # Для атрибута типа module.attribute добавляем module
                    self.names.append(node.value.id)
                self.generic_visit(node)
        
        visitor = DependencyVisitor(self)
        visitor.visit(node)
        return visitor.names

    def _extract_imports(self, module_ast: ast.Module, file_path: Path) -> List[ImportInfo]:
        """
        Извлекает информацию об импортах из AST модуля.
        
        Args:
            module_ast: AST модуля
            file_path: Путь к файлу
            
        Returns:
            Список объектов ImportInfo с информацией об импортах
        """
        imports = []
        
        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                # Обрабатываем простые импорты: import module
                for name in node.names:
                    module_path = self._resolve_import(name.name, file_path)
                    if module_path:
                        imports.append(ImportInfo(
                            module_path=module_path,
                            import_type='import',
                            names=[] # Пустой список, так как импортируем весь модуль
                        ))
            
            elif isinstance(node, ast.ImportFrom):
                # Обрабатываем from ... import: from module import name
                if node.module is not None:
                    module_path = self._resolve_import(node.module, file_path)
                    if module_path:
                        imported_names = [n.name for n in node.names]
                        imports.append(ImportInfo(
                            module_path=module_path,
                            import_type='from',
                            names=imported_names
                        ))
        
        return imports
    
    def _resolve_import(self, import_name: str, importing_file: Path) -> Optional[Path]:
        """
        Преобразует имя импорта в путь к файлу.
        
        Args:
            import_name: Имя импортируемого модуля
            importing_file: Файл, который содержит импорт
            
        Returns:
            Путь к файлу модуля или None, если это внешняя библиотека
        """
        # Проверяем, не является ли импорт внешней библиотекой
        first_part = import_name.split('.')[0]
        if first_part in self.std_libs or first_part in self.external_libs:
            return None
        
        # Получаем директорию импортирующего файла и все родительские директории
        parent_dir = importing_file.parent
        
        # Преобразуем точки в пути директорий
        module_parts = import_name.split('.')
        
        # Список возможных путей для проверки
        possible_paths = []
        
        # 1. Пытаемся найти модуль как локальный импорт в той же директории
        if len(module_parts) == 1:
            possible_paths.append(parent_dir / f"{module_parts[0]}.py")
        
        # 2. Проверяем, не является ли первая часть импорта самим пакетом
        # Ищем корень пакета, двигаясь вверх по дереву директорий
        potential_package_root = parent_dir
        package_roots = []
        
        # Проверяем все родительские директории на наличие __init__.py
        while str(potential_package_root) != str(potential_package_root.parent):
            if (potential_package_root / "__init__.py").exists():
                # Если нашли __init__.py, это может быть корнем пакета
                package_roots.append(potential_package_root)
                
                # Проверяем, совпадает ли имя директории с первой частью импорта
                if potential_package_root.name == first_part:
                    # Это корень пакета с тем же именем, что и импорт
                    # Например, структура: sompath/click/src/click/
                    # Импорт: from click.shell_completion import ...
                    
                    # Строим путь от корня пакета
                    module_path = potential_package_root
                    for part in module_parts[1:]:
                        module_path = module_path / part
                    possible_paths.append(module_path.with_suffix('.py'))
                    
                    # Также проверяем вариант с __init__.py
                    if len(module_parts) > 1:
                        possible_paths.append(module_path / "__init__.py")
            
            potential_package_root = potential_package_root.parent
        
        # 3. Вложенный импорт с учетом всех частей пути
        module_path = parent_dir
        for part in module_parts[:-1]:
            module_path = module_path / part
        module_path = module_path / f"{module_parts[-1]}.py"
        possible_paths.append(module_path)
        
        # 4. Импорт относительно корня проекта
        module_path = '/'.join(module_parts)
        possible_paths.append(self.project_root / f"{module_path}.py")
        
        # 5. Импорт как пакет относительно корня проекта
        possible_paths.append(self.project_root / module_path / "__init__.py")
        
        # 6. Используем все найденные корни пакетов
        for package_root in package_roots:
            module_path = package_root.parent  # Поднимаемся на уровень выше корня пакета
            for part in module_parts:
                module_path = module_path / part
            possible_paths.append(module_path.with_suffix('.py'))
            possible_paths.append(module_path / "__init__.py")
        
        # Устраняем дубликаты в путях
        unique_paths = []
        for path in possible_paths:
            str_path = str(path)
            if str_path not in [str(p) for p in unique_paths]:
                unique_paths.append(path)
        
        # Проверяем все возможные пути
        for path in unique_paths:
            if path.exists():
                return path
        
        # Если мы дошли до сюда, модуль не найден
        print(f"Предупреждение: Модуль {import_name} не найден (импортирован из {importing_file})")
        return None
    
    def _analyze_usage(self, start_file: Path) -> None:
        """
        Анализирует использование импортированных элементов в коде.
        Определяет, какие именно элементы из импортированных модулей используются.
        
        Args:
            start_file: Файл, с которого начинается анализ
        """
        # Создаем словарь для отслеживания, какие имена используются в каждом файле
        used_names = {}
        
        # Функция для анализа использования в одном файле
        def analyze_file_usage(file_path: str):
            if file_path not in self.ast_cache:
                return
            
            file_ast = self.ast_cache[file_path]
            file_used_names = set()
            
            # Visitor для поиска используемых имен
            class NameUsageVisitor(ast.NodeVisitor):
                def __init__(self, collector):
                    self.collector = collector
                    self.used = set()
                
                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Load):
                        self.used.add(node.id)
                    self.generic_visit(node)
                
                def visit_Attribute(self, node):
                    # Для случаев module.attribute
                    if isinstance(node.value, ast.Name):
                        # Запоминаем module
                        self.used.add(node.value.id)
                        # Также запоминаем полное имя module.attribute
                        self.used.add(f"{node.value.id}.{node.attr}")
                    self.generic_visit(node)
            
            visitor = NameUsageVisitor(self)
            visitor.visit(file_ast)
            
            used_names[file_path] = visitor.used
        
        # Анализируем использование импортов, начиная с указанного файла
        for file_path in self.processed_files:
            analyze_file_usage(file_path)
        
        # На основе анализа определяем, какие элементы каждого модуля используются
        for file_path, names in used_names.items():
            # Проверяем каждый импорт
            for module_name, import_info in self.imports.items():
                if import_info.import_type == 'from':
                    # Для 'from module import name' отмечаем используемые имена
                    for name in import_info.names:
                        if name in names:
                            import_info.used_names.add(name)
                else:  # import_info.import_type == 'import'
                    # Для 'import module' ищем использования вида module.attribute
                    module_usages = [n for n in names if n.startswith(f"{module_name}.")]
                    if module_usages or module_name in names:
                        # Если есть прямые обращения к модулю или его атрибутам
                        for usage in module_usages:
                            attr_name = usage.split('.')[1]  # получаем attribute из module.attribute
                            import_info.used_names.add(attr_name)
    
    def _filter_used_elements(self) -> Dict[str, Dict[str, CodeElement]]:
        """
        Фильтрует элементы кода, оставляя только те, которые фактически используются.
        
        Returns:
            Отфильтрованный словарь элементов кода
        """
        filtered_elements = {}
        
        # Для каждого модуля проверяем используемые элементы
        for module_name, elements in self.code_elements.items():
            if module_name not in self.imports:
                # Если модуль - это исходный файл (не импортированный), включаем все его элементы
                filtered_elements[module_name] = elements
                continue
            
            import_info = self.imports[module_name]
            filtered_elements[module_name] = {}

            # если импортирован через 'import' включаем все его элементы
            if import_info.import_type == 'import':
                filtered_elements[module_name] = elements
                continue

            # Включаем все явно импортированные элементы, даже если они не используются 
            for name, element in elements.items():
                if name in import_info.names or name in import_info.used_names:
                    filtered_elements[module_name][name] = element
        
        return filtered_elements
    
    def format_context(self, add_current_file=False) -> str:
        """
        Форматирует собранный контекст в удобный для использования вид.
        Включает только используемые элементы кода.
        
        Returns:
            Строка с отформатированным контекстом
        """
        filtered_elements = self._filter_used_elements()
        context = []
        for module_name, elements in filtered_elements.items():
            # Пропускаем стартовый файл если add_current_file=False
            if not add_current_file and module_name not in self.imports:
                continue

            if module_name in self.imports:
                module_path = self.imports[module_name].module_path
                module_content = [f"# File: {module_path}"]
            else:
                # Для исходного файла или других случаев, когда модуль не в imports
                module_content = [f"# Module: {module_name}"]
            

            # Добавляем элементы модуля
            for element_name, element in elements.items():
                module_content.append(element.source_code)
            
            context.append("\n\n".join(module_content))
        
        return "\n\n".join(context)
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Возвращает содержимое указанного файла из кэша.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Содержимое файла или None, если файл не найден в кэше
        """
        abs_path = str(self._resolve_path(file_path))
        return self.file_cache.get(abs_path)


# Пример использования
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Сбор контекста кода из локальных импортов")
    parser.add_argument("file", help="Путь к файлу, с которого начинать анализ")
    parser.add_argument("--root", help="Корневая директория проекта")
    parser.add_argument("--output", help="Файл для сохранения результата")
    
    args = parser.parse_args()
    
    collector = CodeContextCollector(project_root=args.root)
    context = collector.collect_context(args.file)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(collector.format_context())
        print(f"Контекст сохранен в {args.output}")
    else:
        print("Собранный контекст:")
        print(collector.format_context())
    
    print(f"Всего модулей в контексте: {len(context)}")
    total_elements = sum(len(elements) for elements in context.values())
    print(f"Всего элементов кода: {total_elements}")

