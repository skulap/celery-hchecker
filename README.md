# Celery Health Checker

Компонент для мониторинга здоровья Celery (брокер, бэкенд и воркеры) с кешированием и фоновой проверкой.

## Особенности

✅ Проверка состояния:
- Доступность брокера
- Работоспособность result backend
- Наличие активных воркеров

✅ Дополнительные возможности:
- Кеширование результатов проверок
- Фоновый мониторинг с заданным интервалом
- Thread-safe реализация
- Интеграция с существующим приложением Celery

## Установка
```bash
pip install celery cachetools
```

## Быстрый старт

```python
from celery import Celery
from celery_health_check import CeleryHealthChecker

app = Celery(broker='redis://localhost:6379/0', backend='redis://localhost:6379/1')

# Инициализация
checker = CeleryHealthChecker.create(
    app=app,
    cache_timeout=30,       # TTL кеша в секундах
    inspect_timeout=5,      # Таймаут проверки воркеров
    monitoring_interval=60  # Интервал фоновых проверок
)

# Запуск фонового мониторинга
checker.start_monitoring()

# Проверка статуса
if checker.is_healthy():
    print("Все системы в норме!")
else:
    print("Проблемы с Celery!")

# При завершении приложения
checker.stop_monitoring()
```

## Детали использования

### Методы

1. Прямые проверки:
```python
checker.check_broker()    # → bool
checker.check_backend()   # → bool
checker.check_workers()   # → bool
```
2. Комплексная проверка:
```python
checker.is_healthy()  # → bool (использует кеш)
```

3. Управление мониторингом:
```python
checker.start_monitoring()
checker.stop_monitoring()
```

## Конфигурация

Параметры инициализации:
- `app` - экземпляр Celery приложения
- `cache_timeout` - время жизни кеша (сек)
- `inspect_timeout` - таймаут проверки воркеров (сек)
- `monitoring_interval` - интервал фоновых проверок (сек)
- `backend_check_key` - ключ для проверки бэкенда

## Тестирование
Требования
- Работающий Redis
- Установленные зависимости тестов:
```bash
pip install pytest
```

## Запуск тестов

```bash
pytest tests.py -v
```

### Тесты покрывают:
- Проверку доступности брокера
- Работу с result backend
- Обнаружение воркеров
- Кеширование результатов
- Фоновый мониторинг

## Логирование
Компонент использует стандартный logging с логгером CeleryHealthChecker.
Уровень логирования можно настроить:

```python
import logging
logging.getLogger('CeleryHealthChecker').setLevel(logging.DEBUG)
```

## Ограничения
- Поддерживаются только брокеры/бэкенды, совместимые с Kombu
- Для проверки воркеров требуется доступ к Celery Control API

## Лицензия
MIT License
