#!/usr/bin/env python3
"""
Модуль для обработки и анализа набора данных временных рядов.
Предоставляет функциональность для загрузки, очистки и анализа данных.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Union, Optional
import os
from datetime import datetime

# # Импортируем вспомогательную функцию из второго файла
from example.time_series_utils import detect_anomalies, calculate_seasonal_decomposition
import code_context_collector


class TimeSeriesProcessor:
    """Класс для обработки временных рядов."""
    
    def __init__(self, data_path: str = None):
        """
        Инициализирует процессор временных рядов.
        
        Args:
            data_path: Путь к файлу с данными временного ряда
        """
        self.data_path = data_path
        self.data = None
        self.processed_data = None
        self.anomalies = None
    
    def load_data(self, filepath: Optional[str] = None) -> pd.DataFrame:
        """
        Загружает данные из CSV файла.
        
        Args:
            filepath: Опциональный путь к файлу (если не указан, используется self.data_path)
            
        Returns:
            DataFrame с загруженными данными
        """
        path = filepath or self.data_path
        if not path:
            raise ValueError("Путь к файлу данных не указан")
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Файл {path} не найден")
        
        self.data = pd.read_csv(path, parse_dates=['timestamp'])
        return self.data
    
    def preprocess_data(self) -> pd.DataFrame:
        """
        Выполняет предварительную обработку данных.
        
        Returns:
            DataFrame с обработанными данными
        """
        if self.data is None:
            raise ValueError("Данные не загружены. Сначала выполните load_data()")
        
        # Удаление дубликатов
        self.processed_data = self.data.drop_duplicates()
        
        # Обработка пропущенных значений
        self.processed_data = self.processed_data.interpolate(method='linear')
        
        # Создание дополнительных признаков для временных рядов
        self.processed_data['hour'] = self.processed_data['timestamp'].dt.hour
        self.processed_data['day_of_week'] = self.processed_data['timestamp'].dt.dayofweek
        self.processed_data['is_weekend'] = self.processed_data['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        
        return self.processed_data
    
    def analyze_time_series(self, column: str = 'value', window_size: int = 24) -> Dict:
        """
        Анализирует временной ряд и выявляет аномалии.
        
        Args:
            column: Имя столбца с данными для анализа
            window_size: Размер окна для скользящих статистик
            
        Returns:
            Словарь с результатами анализа
        """
        if self.processed_data is None:
            self.preprocess_data()
        
        results = {}
        
        # Вычисление базовых статистик
        results['basic_stats'] = {
            'mean': float(self.processed_data[column].mean()),
            'median': float(self.processed_data[column].median()),
            'std_dev': float(self.processed_data[column].std()),
            'min': float(self.processed_data[column].min()),
            'max': float(self.processed_data[column].max())
        }
        
        # Скользящие статистики
        self.processed_data['rolling_mean'] = self.processed_data[column].rolling(window=window_size).mean()
        self.processed_data['rolling_std'] = self.processed_data[column].rolling(window=window_size).std()

        # код анализа аномалий
        
        
        # Визуализация результатов
        self._plot_time_series(column)
        
        return results
    
    def _plot_time_series(self, column: str):
        """
        Создает визуализацию временного ряда с выделенными аномалиями.
        
        Args:
            column: Столбец с данными для визуализации
        """
        plt.figure(figsize=(12, 6))
        plt.plot(self.processed_data['timestamp'], self.processed_data[column], label='Данные')
        plt.plot(self.processed_data['timestamp'], self.processed_data['rolling_mean'], 
                 label=f'Скользящее среднее (окно={self.processed_data["rolling_mean"].rolling.window})')
        
        plt.legend()
        plt.title(f'Анализ временного ряда: {column}')
        plt.xlabel('Время')
        plt.ylabel('Значение')
        plt.tight_layout()
        plt.savefig('time_series_analysis.png')
        plt.close()

def main():
    """Пример использования класса TimeSeriesProcessor."""
    processor = TimeSeriesProcessor('data/sensor_readings.csv')
    processor.load_data()
    processor.preprocess_data()
    results = processor.analyze_time_series(column='temperature')
    
    print("Результаты анализа:")
    for key, value in results.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
