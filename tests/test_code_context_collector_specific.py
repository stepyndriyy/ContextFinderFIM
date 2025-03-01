import pytest
import os
import tempfile
import ast
from pathlib import Path
from code_context_collector import CodeContextCollector, ImportInfo, CodeElement


@pytest.fixture
def test_project_structure():
    """
    Создает временную структуру тестового проекта.
    
    Структура:
    test_project/
    ├── main.py                         # Главный файл с разными типами импортов
    ├── simple_module.py                # Простой модуль с функциями
    ├── package1/
    │   ├── __init__.py                 # Инициализация пакета
    │   └── module1.py                  # Модуль в пакете 1
    └── package2/
        ├── __init__.py                 # Инициализация пакета 2
        ├── subpackage/
        │   ├── __init__.py             # Инициализация подпакета
        │   └── module2.py              # Модуль во вложенном пакете
        └── utils.py                    # Утилиты в пакете 2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем корневую директорию проекта
        project_root = Path(temp_dir) / "test_project"
        project_root.mkdir()
        
        # Создаем пакеты и их директории
        package1_dir = project_root / "package1"
        package1_dir.mkdir()
        
        package2_dir = project_root / "package2"
        package2_dir.mkdir()
        
        subpackage_dir = package2_dir / "subpackage"
        subpackage_dir.mkdir()
        
        # Создаем файлы __init__.py для пакетов
        with open(package1_dir / "__init__.py", "w") as f:
            f.write("# Package 1 initialization\n")
        
        with open(package2_dir / "__init__.py", "w") as f:
            f.write("# Package 2 initialization\n")
        
        with open(subpackage_dir / "__init__.py", "w") as f:
            f.write("# Subpackage initialization\n")
        
        # Создаем простой модуль
        with open(project_root / "simple_module.py", "w") as f:
            f.write("""
def simple_function():
    return "I'm a simple function"

class SimpleClass:
    def __init__(self):
        self.value = "Simple class instance"
    
    def get_value(self):
        return self.value

SIMPLE_CONSTANT = "I'm a simple constant"
""")
        
        # Создаем module1.py в package1
        with open(package1_dir / "module1.py", "w") as f:
            f.write("""
from package2.utils import utility_function

def module1_function():
    return "Module 1 function: " + utility_function()

class Module1Class:
    def process(self):
        return "Processing in Module1Class"
""")
        
        # Создаем utils.py в package2
        with open(package2_dir / "utils.py", "w") as f:
            f.write("""
def utility_function():
    return "Utility function called"

def another_utility():
    return "Another utility function"

UTILS_CONSTANT = "Utils constant value"
""")
        
        # Создаем module2.py в subpackage
        with open(subpackage_dir / "module2.py", "w") as f:
            f.write("""
from package1.module1 import module1_function

def deep_function():
    return "Deep function with " + module1_function()

class DeepClass:
    def deep_method(self):
        return "Deep method result"
""")
        
        # Создаем главный файл с различными типами импортов
        with open(project_root / "main.py", "w") as f:
            f.write("""
# Простые импорты
import simple_module
from simple_module import simple_function, SimpleClass

# Импорты с пакетами
import package1.module1
from package1.module1 import module1_function, Module1Class

# Импорты из вложенных пакетов
import package2.subpackage.module2
from package2.subpackage.module2 import deep_function

# Импорты только объявленные, но не используемые
from package2.utils import another_utility, UTILS_CONSTANT

def main():
    # Используем импортированные функции и классы
    print(simple_function())
    simple_class = SimpleClass()
    print(simple_class.get_value())
    
    # Используем функцию из пакета
    print(module1_function())
    
    # Используем класс из пакета
    module1_class = Module1Class()
    print(module1_class.process())
    
    # Используем функцию из вложенного пакета
    print(deep_function())
    
    # Используем модуль, импортированный целиком
    print(simple_module.SIMPLE_CONSTANT)
    
    return "Main function completed"
""")
        
        yield project_root


class TestResolveImports:
    """Тесты для метода _resolve_import."""
    
    def test_simple_import_resolution(self, test_project_structure):
        """Тест для разрешения простого импорта."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        # Тестируем разрешение простого модуля
        main_file = test_project_structure / "main.py"
        resolved_path = collector._resolve_import("simple_module", main_file)
        
        assert resolved_path is not None
        assert resolved_path.name == "simple_module.py"
        assert resolved_path.parent == test_project_structure
    
    def test_package_import_resolution(self, test_project_structure):
        """Тест для разрешения импорта из пакета."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        # Тестируем разрешение модуля из пакета
        main_file = test_project_structure / "main.py"
        resolved_path = collector._resolve_import("package1.module1", main_file)
        
        assert resolved_path is not None
        assert resolved_path.name == "module1.py"
        assert resolved_path.parent == test_project_structure / "package1"
    
    def test_nested_package_import_resolution(self, test_project_structure):
        """Тест для разрешения импорта из вложенного пакета."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        # Тестируем разрешение модуля из вложенного пакета
        main_file = test_project_structure / "main.py"
        resolved_path = collector._resolve_import("package2.subpackage.module2", main_file)
        
        assert resolved_path is not None
        assert resolved_path.name == "module2.py"
        assert resolved_path.parent == test_project_structure / "package2/subpackage"
    
    def test_relative_import_resolution(self, test_project_structure):
        """Тест для разрешения относительного импорта."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        # Тестируем разрешение относительного импорта
        module1_file = test_project_structure / "package1/module1.py"
        resolved_path = collector._resolve_import("package2.utils", module1_file)
        
        assert resolved_path is not None
        assert resolved_path.name == "utils.py"
        assert resolved_path.parent == test_project_structure / "package2"
    
    def test_nonexistent_import_resolution(self, test_project_structure):
        """Тест для проверки обработки несуществующих импортов."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        main_file = test_project_structure / "main.py"
        resolved_path = collector._resolve_import("nonexistent_module", main_file)
        
        assert resolved_path is None


class TestFilterUsedElements:
    """Тесты для метода _filter_used_elements."""
    
    def setup_collector_with_mocks(self, test_project_structure):
        """Настраивает коллектор с моками для тестирования _filter_used_elements."""
        collector = CodeContextCollector(project_root=test_project_structure)
        
        # Создаем моки для элементов кода
        collector.code_elements = {
            "simple_module": {
                "simple_function": CodeElement(
                    name="simple_function",
                    element_type="function",
                    source_code="def simple_function():\n    return 'Simple function'"
                ),
                "SimpleClass": CodeElement(
                    name="SimpleClass",
                    element_type="class",
                    source_code="class SimpleClass:\n    pass"
                ),
                "SIMPLE_CONSTANT": CodeElement(
                    name="SIMPLE_CONSTANT",
                    element_type="constant",
                    source_code="SIMPLE_CONSTANT = 'Simple constant'"
                )
            },
            "package2.utils": {
                "utility_function": CodeElement(
                    name="utility_function",
                    element_type="function",
                    source_code="def utility_function():\n    return 'Utility function'"
                ),
                "another_utility": CodeElement(
                    name="another_utility",
                    element_type="function",
                    source_code="def another_utility():\n    return 'Another utility'"
                ),
                "UTILS_CONSTANT": CodeElement(
                    name="UTILS_CONSTANT",
                    element_type="constant",
                    source_code="UTILS_CONSTANT = 'Utils constant'"
                )
            }
        }
        
        # Создаем моки для информации об импортах
        simple_module_path = test_project_structure / "simple_module.py"
        utils_module_path = test_project_structure / "package2/utils.py"
        
        collector.imports = {
            "simple_module": ImportInfo(
                module_path=simple_module_path,
                import_type="import",
                names=[]
            ),
            "package2.utils": ImportInfo(
                module_path=utils_module_path,
                import_type="from",
                names=["utility_function", "another_utility", "UTILS_CONSTANT"]
            )
        }
        
        # Устанавливаем используемые имена
        collector.imports["simple_module"].used_names = {"simple_function", "SIMPLE_CONSTANT"}
        collector.imports["package2.utils"].used_names = {"utility_function"}
        
        return collector
    
    def test_import_whole_module(self, test_project_structure):
        """Тест для фильтрации при импорте целого модуля."""
        collector = self.setup_collector_with_mocks(test_project_structure)
        
        # Вызываем метод _filter_used_elements
        filtered_elements = collector._filter_used_elements()
        
        # Проверяем, что для импорта "import module" включены все элементы
        assert "simple_module" in filtered_elements
        assert len(filtered_elements["simple_module"]) == 3  # Все элементы модуля
        assert "simple_function" in filtered_elements["simple_module"]
        assert "SimpleClass" in filtered_elements["simple_module"]
        assert "SIMPLE_CONSTANT" in filtered_elements["simple_module"]
    
    def test_from_import_filtering(self, test_project_structure):
        """Тест для фильтрации при импорте 'from module import name'."""
        collector = self.setup_collector_with_mocks(test_project_structure)
        
        # Вызываем метод _filter_used_elements
        filtered_elements = collector._filter_used_elements()
        
        # Проверяем, что для импорта "from module import name" включены только указанные элементы
        assert "package2.utils" in filtered_elements
        assert len(filtered_elements["package2.utils"]) == 3  # Все импортированные элементы
        assert "utility_function" in filtered_elements["package2.utils"]  # Используемый элемент
        assert "another_utility" in filtered_elements["package2.utils"]  # Не используемый, но импортированный
        assert "UTILS_CONSTANT" in filtered_elements["package2.utils"]   # Не используемый, но импортированный
    
    def test_unused_imports_inclusion(self, test_project_structure):
        """Тест для проверки включения неиспользуемых, но явно импортированных элементов."""
        collector = self.setup_collector_with_mocks(test_project_structure)
        
        # Модифицируем моки чтобы имитировать ситуацию с неиспользуемыми импортами
        collector.imports["package2.utils"].used_names = set()  # Пустое множество используемых имен
        
        # Вызываем метод _filter_used_elements
        filtered_elements = collector._filter_used_elements()
        
        # Проверяем, что явно импортированные элементы все равно включены
        assert "package2.utils" in filtered_elements
        assert len(filtered_elements["package2.utils"]) == 3  # Все импортированные элементы включены
        assert "utility_function" in filtered_elements["package2.utils"]
        assert "another_utility" in filtered_elements["package2.utils"]
        assert "UTILS_CONSTANT" in filtered_elements["package2.utils"]
    
    def test_partial_imports_filtering(self, test_project_structure):
        """Тест для проверки частичного включения импортов."""
        collector = self.setup_collector_with_mocks(test_project_structure)
        
        # Изменяем список импортированных имен, имитируя частичный импорт
        collector.imports["package2.utils"].names = ["utility_function"]  # Импортирована только одна функция
        
        # Вызываем метод _filter_used_elements
        filtered_elements = collector._filter_used_elements()
        
        # Проверяем, что включен только явно импортированный элемент
        assert "package2.utils" in filtered_elements
        assert len(filtered_elements["package2.utils"]) == 1  # Только один элемент
        assert "utility_function" in filtered_elements["package2.utils"]
        assert "another_utility" not in filtered_elements["package2.utils"]
        assert "UTILS_CONSTANT" not in filtered_elements["package2.utils"]