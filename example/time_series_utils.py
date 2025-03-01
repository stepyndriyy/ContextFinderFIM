#!/usr/bin/env python3
"""
Вспомогательные функции для анализа временных рядов.
Содержит алгоритмы обнаружения аномалий и статистической обработки.
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Union, Optional


def detect_anomalies(data: pd.DataFrame, value_column: str, 
                    rolling_mean_column: str = 'rolling_mean',
                    rolling_std_column: str = 'rolling_std',
                    threshold: float = 3.0) -> Tuple[pd.DataFrame, Dict[str, any]]:
    """
    Обнаруживает аномалии во временном ряду с использованием Z-score метода.
    
    Эта функция ищет наблюдения, которые значительно отклоняются от 
    типичного поведения временного ряда. Для этого используется метод
    Z-score, который определяет, насколько каждое значение отличается
    от скользящего среднего в единицах стандартного отклонения.
    
    Args:
        data: DataFrame с данными временного ряда
        value_column: Имя столбца со значениями для анализа
        rolling_mean_column: Имя столбца со скользящим средним
        rolling_std_column: Имя столбца со скользящим стандартным отклонением
        threshold: Пороговое значение Z-score для определения аномалии
    
    Returns:
        Tuple, содержащий:
        - DataFrame с добавленными столбцами 'z_score' и 'is_anomaly'
        - Словарь со статистикой найденных аномалий
    """
    # Проверка наличия необходимых столбцов
    required_columns = [value_column, rolling_mean_column, rolling_std_column]
    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"Столбец {col} отсутствует в данных")
    
    # Делаем копию данных, чтобы не модифицировать оригинал
    result_data = data.copy()
    
    # Вычисляем Z-score для каждого наблюдения
    result_data['z_score'] = np.abs((result_data[value_column] - result_data[rolling_mean_column]) / 
                                   result_data[rolling_std_column])
    
    # Определяем аномалии как наблюдения с Z-score выше порогового значения
    result_data['is_anomaly'] = result_data['z_score'] > threshold
    
    # Соберем статистику по аномалиям
    anomalies = result_data[result_data['is_anomaly']]
    anomaly_stats = {
        'total_count': len(anomalies),
        'percentage': len(anomalies) / len(result_data) * 100,
        'max_z_score': float(anomalies['z_score'].max()) if not anomalies.empty else 0,
        'min_z_score': float(anomalies['z_score'].min()) if not anomalies.empty else 0,
        'mean_z_score': float(anomalies['z_score'].mean()) if not anomalies.empty else 0,
        'anomaly_timestamps': anomalies['timestamp'].tolist() if 'timestamp' in anomalies.columns else []
    }
    
    return result_data, anomaly_stats


def calculate_seasonal_decomposition(data: pd.DataFrame, 
                                    value_column: str,
                                    timestamp_column: str = 'timestamp',
                                    period: Optional[int] = None) -> Dict[str, np.ndarray]:
    """
    Выполняет сезонную декомпозицию временного ряда.
    
    Args:
        data: DataFrame с данными временного ряда
        value_column: Имя столбца со значениями для анализа
        timestamp_column: Имя столбца с временными метками
        period: Период сезонности (если None, будет определен автоматически)
    
    Returns:
        Словарь с компонентами временного ряда: тренд, сезонность, остаток
    """
    # Проверка на наличие необходимых библиотек
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
    except ImportError:
        raise ImportError("Для использования этой функции необходимо установить statsmodels")
    
    # Проверка наличия необходимых столбцов
    required_columns = [value_column, timestamp_column]
    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"Столбец {col} отсутствует в данных")
    
    # Определяем период автоматически, если не указан
    if period is None:
        # Простой эвристический метод: предполагаем дневные данные с недельной сезонностью
        time_diff = data[timestamp_column].diff().dt.total_seconds().median()
        if time_diff < 60:  # Данные с минутным разрешением
            period = 1440  # 24 часа * 60 минут
        elif time_diff < 3600:  # Данные с часовым разрешением
            period = 24  # 24 часа
        else:  # Данные с дневным разрешением
            period = 7  # 7 дней
    
    # Преобразуем DataFrame для декомпозиции
    ts = data.set_index(timestamp_column)[value_column]
    
    # Выполняем декомпозицию
    result = seasonal_decompose(ts, model='additive', period=period)
    
    # Возвращаем результаты в виде словаря
    return {
        'trend': result.trend.values,
        'seasonal': result.seasonal.values,
        'residual': result.resid.values,
        'period': period
    }
