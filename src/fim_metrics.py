"""
Функции для расчета метрик сравнения кода.
"""
import difflib
from typing import Dict, Any
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

def calculate_metrics(generated_code: str, original_code: str) -> Dict[str, float]:
    """
    Рассчитывает метрики для сравнения сгенерированного и оригинального кода.
    
    Args:
        generated_code: Сгенерированный код
        original_code: Оригинальный код
        
    Returns:
        Словарь с метриками
    """
    # Проверяем, установлены ли нужные ресурсы NLTK
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    
    # Токенизация кода
    smoother = SmoothingFunction().method1
    gen_tokens = generated_code.split()
    orig_tokens = original_code.split()
    
    # Вычисляем BLEU с разными весами n-грамм
    bleu_1 = sentence_bleu([orig_tokens], gen_tokens, weights=(1, 0, 0, 0), smoothing_function=smoother)
    bleu_2 = sentence_bleu([orig_tokens], gen_tokens, weights=(0.5, 0.5, 0, 0), smoothing_function=smoother)
    bleu_4 = sentence_bleu([orig_tokens], gen_tokens, weights=(0.25, 0.25, 0.25, 0.25), smoothing_function=smoother)
    
    # Рассчитываем ROUGE
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=False)
    rouge_scores = scorer.score(original_code, generated_code)
    
    # Рассчитываем сходство по Левенштейну
    sim_ratio = difflib.SequenceMatcher(None, original_code, generated_code).ratio()
    
    # Собираем все метрики
    metrics = {
        "bleu_1": bleu_1,
        "bleu_2": bleu_2,
        "bleu_4": bleu_4,
        "rouge1_precision": rouge_scores['rouge1'].precision,
        "rouge1_recall": rouge_scores['rouge1'].recall,
        "rouge1_fmeasure": rouge_scores['rouge1'].fmeasure,
        "rouge2_fmeasure": rouge_scores['rouge2'].fmeasure,
        "rougeL_fmeasure": rouge_scores['rougeL'].fmeasure,
        "levenshtein_similarity": sim_ratio
    }
    
    return metrics
