# Улучшение работы LLM модели в задаче FIM при помощи подбора релевантного контекста

Написать Нормальный ридми

Пофиксить проблемку с тем что в cli -project_root и путь до файла могут пересекаться в пути, тогда пути не правильно резолвятся

То есть сейчас работают только абсолютные пути как аргумент project_root

Глобально по всему проекту какие то проблемы с резолвингом путей

Пофиксить _process_file d code_context_collector


Как запускать

```
python src/evaluate_fim_with_context.py --dataset datasets/code_transformations/ --project-root /home/belyakov.si/personal/diploma/projects/click/src --output results/click_res_test2.json
```

