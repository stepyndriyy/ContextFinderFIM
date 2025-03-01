import torch
from code_llama_fim import CodeLlamaFIM

if __name__ == "__main__":
    # Инициализация модели
    llm = CodeLlamaFIM(
        model_path="codellama/CodeLlama-7b-hf",
        cache_dir="models/"
    )
    
    # Пример файла с кодом
    file_path = "example.py"  # Укажите путь к своему файлу
    
    # Позиция курсора, где вы хотите вставить код
    cursor_position = 100  # Это зависит от вашего файла
    
    # Запрос на завершение кода
    generated_code = llm.complete_code(
        file_path=file_path,
        cursor_position=cursor_position,
        max_new_tokens=150
    )
    
    print("Сгенерированный код:")
    print(generated_code)
    
    # Получение нескольких вариантов
    suggestions = llm.suggest_completions(
        file_path=file_path,
        cursor_position=cursor_position,
        num_suggestions=3
    )
    
    print("\nВарианты завершения:")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"Вариант {i}:")
        print(suggestion)
        print("-" * 50)
