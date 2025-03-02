"""
Трансформатор для удаления тела функции.

Удаляет тело функции, оставляя только заголовок и, 
опционально, документацию и заглушку (pass).
"""
import ast
import copy
import random
from typing import Dict, Any, List, Tuple, Optional

from benchmark_tool.src.transformers.base import CodeTransformer, TransformerRegistry
import ast_parser

class FunctionBodyRemover(CodeTransformer):
    """Трансформатор, удаляющий тело функции, оставляя только сигнатуру."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация трансформатора.
        
        Args:
            config: Конфигурация трансформатора
        """
        super().__init__(config)
        self.min_body_lines = config.get('min_body_lines', 3)
        self.keep_docstring = config.get('keep_docstring', True)
        self.add_pass = config.get('add_pass', True)
        
    def can_transform(self, node: ast.AST) -> bool:
        """
        Проверяет, может ли функция быть трансформирована.
        
        Критерии:
        - Узел должен быть функцией
        - Тело функции должно быть достаточно большим (не менее min_body_lines)
        - Функция не должна быть магическим методом (начинаться и заканчиваться '__')
        
        Args:
            node: Узел AST для проверки
            
        Returns:
            True, если функция может быть трансформирована
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        
        # Пропускаем магические методы
        if node.name.startswith('__') and node.name.endswith('__'):
            return False
        
        # Проверяем размер тела функции
        return len(node.body) >= self.min_body_lines

    # Add this to your FunctionBodyRemover class
    def remove_function_body(self, node: ast.FunctionDef, original_code: str) -> Tuple[str, Dict[str, Any]]:
        """
        Replaces just the function body in the original source while preserving all other formatting.
        
        Args:
            node: Function node to transform
            original_code: Original source code
            
        Returns:
            Tuple of transformed code and metadata
        """
        try:
            # Get function source line numbers
            func_start = node.lineno - 1  # Lines are 0-indexed for our array
            func_end = node.end_lineno if hasattr(node, 'end_lineno') else None
            
            # Split code into lines
            lines = original_code.splitlines(True)  # Keep line endings
            
            # Find where function header ends (the line with the colon after all parameters)
            header_end = -1
            paren_count = 0
            in_signature = False
            
            for i in range(func_start, len(lines)):
                line = lines[i]
                
                # Track opening and closing parentheses to handle multi-line parameters
                for char in line:
                    if char == '(':
                        in_signature = True
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0 and in_signature:
                            in_signature = False
                
                # Check for the end of the function definition
                if ':' in line and not in_signature and paren_count == 0:
                    header_end = i
                    break
            
            if header_end == -1:
                return original_code, {"success": False, "reason": "Could not locate end of function header"}
            
            # Now find the actual first line of code (skipping blank lines)
            # This is the true body_start
            actual_body_start = header_end + 1
            while actual_body_start < len(lines) and not lines[actual_body_start].strip():
                actual_body_start += 1
            
            if actual_body_start >= len(lines):
                return original_code, {"success": False, "reason": "No function body found"}
            
            # Find the indentation level from the first non-empty line
            indentation = len(lines[actual_body_start]) - len(lines[actual_body_start].lstrip())
            
            # Find end of function (where indentation returns to previous level)
            body_end = func_end
            if body_end is None:
                for i in range(actual_body_start + 1, len(lines)):
                    line_content = lines[i].strip()
                    if line_content:  # Skip empty lines
                        cur_indent = len(lines[i]) - len(lines[i].lstrip())
                        if cur_indent <= indentation:
                            body_end = i
                            break
            
            if body_end is None:
                body_end = len(lines)
            
            # All lines between header_end+1 and body_end are part of the function body
            # Including blank lines after the header
            body_start = header_end + 1
            body_lines = lines[body_start:body_end]
            body_text = ''.join(body_lines)
            
            # Create replacement preserving whitespace after header
            replacement_lines = []
            
            # Add blank lines that appear right after the header
            for i in range(body_start, actual_body_start):
                replacement_lines.append(lines[i])
            
            # Check for docstring and include it if needed
            has_docstring = False
            if self.keep_docstring and len(node.body) > 0 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
                has_docstring = True
                docstring_node = node.body[0]
                docstring_start = docstring_node.lineno - 1  # Convert to 0-indexed
                docstring_end = docstring_node.end_lineno if hasattr(docstring_node, 'end_lineno') else docstring_start + 1
                
                # Only add docstring lines that haven't been added yet
                for i in range(max(docstring_start, actual_body_start), docstring_end):
                    if i < len(lines):
                        replacement_lines.append(lines[i])
            
            # Add pass statement with correct indentation
            if self.add_pass:
                if replacement_lines and replacement_lines[-1].strip():
                    # Add a newline if the last line isn't empty
                    replacement_lines.append('\n')
                replacement_lines.append(' ' * indentation + 'pass\n')
            
            # Construct transformed code
            transformed_lines = lines[:body_start] + replacement_lines + lines[body_end:]
            transformed_code = ''.join(transformed_lines)
            
            # Calculate cursor position - should be at the indentation level of the actual body
            # If there's a docstring, cursor should be after it
            cursor_line = actual_body_start
            if has_docstring:
                docstring_end_line = node.body[0].end_lineno - 1 if hasattr(node.body[0], 'end_lineno') else node.body[0].lineno
                cursor_line = docstring_end_line + 1
                # Skip any blank lines after the docstring
                while cursor_line < body_end and not lines[cursor_line].strip():
                    cursor_line += 1
            
            # Calculate absolute position for cursor
            cursor_position = 0
            for i in range(cursor_line):
                if i < len(lines):
                    cursor_position += len(lines[i])
            cursor_position += indentation
            
            metadata = {
                "success": True,
                "function_name": node.name,
                "line_number": node.lineno,
                "original_body_size": len(node.body),
                "removed_body": body_text,
                "fim_cursor_line": cursor_line + 1,  # 1-indexed for external tools
                "fim_cursor_column": indentation + 1,  # 1-indexed for external tools
                "fim_cursor_position": cursor_position,
                "original_body_start_line": body_start + 1,  # The actual start line including whitespace
                "original_body_end_line": body_end + 1,
                "actual_code_start_line": actual_body_start + 1,  # The first line with actual code
                "transformed_body_start_line": body_start + 1,
                "transformed_body_end_line": body_start + len(replacement_lines) + 1,
                "type": "function_body_removal"
            }
            
            return transformed_code, metadata
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return original_code, {"success": False, "reason": f"Error in remove_function_body: {str(e)}"}


    def transform(self, ast_tree: ast.Module) -> Tuple[ast.Module, Dict[str, Any]]:
        """
        Applies transformation to AST tree.
    
        Args:
            ast_tree: AST tree for transformation
        
        Returns:
            Tuple of transformed AST and metadata
        """
        # Create a copy of the tree
        new_tree = copy.deepcopy(ast_tree)
    
        # Find all functions
        functions, methods = ast_parser.find_functions(new_tree)
        all_functions = functions + methods
    
        # Filter functions that can be transformed
        transformable_functions = [f for f in all_functions if self.can_transform(f)]
    
        # If no suitable functions, return original tree
        if not transformable_functions:
            return new_tree, {"success": False, "reason": "No suitable functions found"}
    
        # Choose a function to transform
        function_to_transform = random.choice(transformable_functions)
    
        # Get the original source code of the entire file
        # We need to retrieve this from the parse context or pass it as a parameter
        # For now, let's add a method in our apply_transformation that handles this
    
        # This will be modified in the apply_transformation method
        return new_tree, {"function_to_transform": function_to_transform}


# Регистрируем трансформатор
TransformerRegistry.register("function_body", FunctionBodyRemover)
