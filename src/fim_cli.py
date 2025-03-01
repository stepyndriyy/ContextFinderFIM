import argparse
import os
from code_llama_fim import CodeLlamaFIM

def main():
    parser = argparse.ArgumentParser(description="CodeLlama Fill-in-the-Middle CLI")
    
    parser.add_argument("file_path", help="Путь к файлу с кодом")
    parser.add_argument("--line", type=int, help="Номер строки курсора", required=False)
    parser.add_argument("--column", type=int, help="Номер колонки курсора", required=False)
    parser.add_argument("--cursor", type=int, help="Позиция курсора в файле", required=False)
    parser.add_argument("--suggestions", type=int, default=1, help="Количество вариантов (по умолчанию: 1)")
    parser.add_argument("--max-tokens", type=int, default=150, help="Максимальное количество токенов (по умолчанию: 150)")
    parser.add_argument("--model", default="codellama/CodeLlama-7b-hf", help="Модель для использования")
    parser.add_argument("--cache-dir", default="models/", help="Директория для кэширования модели")
    parser.add_argument("--project-root", help="Корневая директория проекта для сбора контекста")
    parser.add_argument("--no-context", action="store_true", help="Не использовать контекст проекта")
    
    
    args = parser.parse_args()
    
    # Проверка существования файла
    if not os.path.exists(args.file_path):
        print(f"Ошибка: Файл {args.file_path} не найден.")
        return
    
    # Преобразование строки и колонки в позицию курсора, если указаны
    if args.line is not None and args.column is not None and args.cursor is None:
        cursor_position = 0
        with open(args.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if args.line > len(lines):
            print(f"Ошибка: в файле всего {len(lines)} строк")
            return
        
        # Суммируем длины предыдущих строк
        for i in range(args.line - 1):
            cursor_position += len(lines[i])
        
        # Добавляем колонку (с учетом индексации с 1)
        cursor_position += args.column - 1
        args.cursor = cursor_position
    
    print(f"Используемые аргументы: {args}")
    # Инициализация модели
    llm = CodeLlamaFIM(
        model_path=args.model,
        cache_dir=args.cache_dir,
        project_root=args.project_root
    )
    
    # Определяем, использовать ли контекст проекта
    use_context = not args.no_context
    
    if args.suggestions == 1:
        # Запрос на одно завершение
        generated_code = llm.complete_code(
            file_path=args.file_path,
            cursor_position=args.cursor,
            max_new_tokens=args.max_tokens,
            use_project_context=use_context
        )
        
        print("\nСгенерированный код:")
        print(generated_code)
    else:
        # Запрос на несколько вариантов
        suggestions = llm.suggest_completions(
            file_path=args.file_path,
            cursor_position=args.cursor,
            num_suggestions=args.suggestions,
            max_new_tokens=args.max_tokens
        )
        
        print("\nВарианты завершения:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\nВариант {i}:")
            print(suggestion)
            print("-" * 50)

if __name__ == "__main__":
    main()
