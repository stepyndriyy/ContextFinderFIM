import sys

def get_cursor_position(file_path, line, column):
    """
    Получает позицию курсора в виде индекса символа по номеру строки и колонки.
    Строки и колонки нумеруются с 1 (как в большинстве редакторов).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if line > len(lines):
        print(f"Ошибка: в файле всего {len(lines)} строк")
        return None
    
    position = 0
    # Суммируем длины предыдущих строк
    for i in range(line - 1):
        position += len(lines[i])
    
    # Добавляем колонку (с учетом индексации с 0)
    position += column - 1
    
    return position

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Использование: python get_cursor_position.py <файл> <строка> <колонка>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    line = int(sys.argv[2])
    column = int(sys.argv[3])
    
    position = get_cursor_position(file_path, line, column)
    if position is not None:
        print(f"Позиция курсора: {position}")
