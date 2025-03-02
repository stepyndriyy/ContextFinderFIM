import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import List, Tuple, Optional, Dict
from code_context_collector import CodeContextCollector


class CodeLlamaFIM:
    def __init__(self, model_path: str = "codellama/CodeLlama-7b-hf", cache_dir: str = "models/", device: str = None, project_root: Optional[str] = None):
        """
        Инициализация CodeLlama для Fill-in-the-Middle задачи.
        
        Args:
            model_path: Путь или идентификатор модели
            cache_dir: Директория для кэширования модели
            device: Устройство для запуска модели ('cuda', 'cpu' или None - автоопределение)
        """
        self.cache_dir = cache_dir
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        print(f"Загрузка токенизатора из {model_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, 
            cache_dir=cache_dir,
            trust_remote_code=True
        )
        
        # Установка pad_token, если он не определен
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print(f"Загрузка модели на устройство {self.device}...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
            cache_dir=cache_dir,
            trust_remote_code=True
        ).to(self.device)
        
        print("Модель успешно загружена!")

        # Инициализация сборщика контекста кода
        self.context_collector = CodeContextCollector(project_root=project_root)
        
        # Кэш контекста для избегания повторного сбора
        self.context_cache = {}
    
    
    def _get_file_context(self, file_path: str, cursor_position: int, window_size: int = 1000) -> Tuple[str, str]:
        """
        Получает контекст из файла на основе позиции курсора.
        
        Args:
            file_path: Путь к файлу
            cursor_position: Позиция курсора в файле (индекс символа)
            window_size: Максимальный размер контекста с каждой стороны
            
        Returns:
            Tuple[str, str]: Префикс и суффикс для Fill-in-the-Middle
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл {file_path} не найден.")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if cursor_position > len(content):
            cursor_position = len(content)
        
        # Получаем префикс (код до курсора) и суффикс (код после курсора)
        prefix = content[:cursor_position]
        suffix = content[cursor_position:]
        
        # Ограничиваем размер контекста
        if len(prefix) > window_size:
            prefix = prefix[-window_size:]
        if len(suffix) > window_size:
            suffix = suffix[:window_size]
        
        return prefix, suffix
    
    def _collect_project_context(self, file_path: str) -> str:
        """
        Собирает контекст из всех связанных файлов проекта.
        
        Args:
            file_path: Путь к файлу, для которого собирается контекст
            
        Returns:
            str: Собранный контекст из всех зависимостей
        """
        # Проверяем кэш сначала
        abs_path = os.path.abspath(file_path)
        if abs_path in self.context_cache:
            return self.context_cache[abs_path]
        
        # Собираем новый контекст
        file_contexts = self.context_collector.collect_context(file_path)
        
        # # Исключаем сам файл из контекста, так как он будет обрабатываться отдельно
        # if abs_path in file_contexts:
        #     del file_contexts[abs_path]
        
        # # Формируем контекст в виде строки
        # context_text = ""
        # for path, content in file_contexts.items():
        #     # Добавляем путь и содержимое в контекст
        #     rel_path = os.path.relpath(path, os.path.dirname(abs_path))
        #     context_text += f"# Файл: {rel_path}\n{content}\n\n"
        context_text = self.context_collector.format_context(add_current_file=False)

        # Сохраняем в кэш
        self.context_cache[abs_path] = context_text
        
        return context_text
    
    def complete_code(self, 
                     file_path: str, 
                     cursor_position: int, 
                     max_new_tokens: int = 128, 
                     temperature: float = 0.05,
                     top_p: float = 0.9,
                     use_project_context: bool = True) -> str:
        """
        Генерирует код для вставки в указанную позицию курсора.
        
        Args:
            file_path: Путь к файлу
            cursor_position: Позиция курсора в файле
            max_new_tokens: Максимальное количество новых токенов для генерации
            temperature: Температура для сэмплирования
            top_p: Параметр top-p сэмплирования
            
        Returns:
            str: Сгенерированный код для вставки
        """
        prefix, suffix = self._get_file_context(file_path, cursor_position, window_size=2000)

        # Если нужно использовать контекст проекта, добавляем его к префиксу
        if use_project_context:
            project_context = self._collect_project_context(file_path)
            # Если контекст не пустой, добавляем его в начало префикса
            if project_context:
                # Если префикс уже большой, используем только начало контекста
                max_context_length = 10000  # Ограничиваем длину контекста
                if len(project_context) > max_context_length:
                    project_context = project_context[:max_context_length] + "\n# ... (context missed)\n\n"
                
                prefix = f"{project_context}\n\n# Current file{os.path.basename(file_path)}\n{prefix}"
        
        # Сохраняем оригинальный промпт для отладки
        original_prompt = f"{prefix} <FILL_ME> {suffix}"
        print(original_prompt)
        # Токенизируем входной текст
        input_ids = self.tokenizer(original_prompt, return_tensors="pt")["input_ids"].to(self.device)
        input_length = input_ids.shape[1]  # Длина входного текста в токенах
        print(f'{input_length=}')
        
        # Генерация кода
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                # temperature=temperature,
                # top_p=top_p,
                # do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id
            )

        # TODO перенести это в self
        token_pre_id, token_mid_id, token_suf_id, token_eot_id = self.tokenizer.convert_tokens_to_ids(self.tokenizer.special_tokens_map['additional_special_tokens'])
        # self.tokenizer._mid 32009

        all_output = outputs[0]
        # Find positions of special tokens in token ids
        mid_pos = (all_output == token_mid_id).nonzero().item()
        # TODO код дерьма, надо поправить
        try:
            eot_pos = (all_output == token_eot_id).nonzero().item()
        except:
            eot_pos = len(all_output)
        generated_code = self.tokenizer.decode(all_output[mid_pos:eot_pos], skip_special_tokens=True)

        return generated_code
    
    def suggest_completions(self, 
                           file_path: str, 
                           cursor_position: int, 
                           num_suggestions: int = 3,
                           max_new_tokens: int = 100,
                           use_project_context: bool = True) -> List[str]:
        """
        Генерирует несколько вариантов завершения кода.
        
        Args:
            file_path: Путь к файлу
            cursor_position: Позиция курсора
            num_suggestions: Количество вариантов завершения
            max_new_tokens: Максимальное количество новых токенов для каждого варианта
            
        Returns:
            List[str]: Список сгенерированных вариантов кода
        """
        suggestions = []
        
        for _ in range(num_suggestions):
            # Для разнообразия используем разную температуру для каждого предложения
            temperature = 0.20
            # temperature = 0.2 + (0.3 * _ / num_suggestions)
            suggestion = self.complete_code(
                file_path=file_path,
                cursor_position=cursor_position,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                use_project_context=use_project_context,
            )
            suggestions.append(suggestion)
        
        return suggestions
