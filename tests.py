import pytest
import threading
import time
import logging
from celery import Celery
from src.celery_hchecker import CeleryHealthChecker

# Ensure logging during tests
logging.basicConfig(level=logging.DEBUG)

# Настройки вашего окружения
BROKER_URL = "redis://:xWni3j@localhost:6348/0"
RESULT_BACKEND = "redis://:xWni3j@localhost:6348/1"


@pytest.fixture(scope="module")
def real_celery_app():
    """
    Создаём реальный экземпляр Celery, как в вашем проекте.
    Требует доступного Redis по указанным урлам.
    """
    app = Celery("test_app", broker=BROKER_URL, backend=RESULT_BACKEND)
    app.conf.task_serializer = 'json'
    app.conf.accept_content = ['json']
    app.conf.result_serializer = 'json'
    yield app


@pytest.fixture(autouse=True)
def reset_singleton():
    """Сбрасываем singleton перед каждым тестом"""
    CeleryHealthChecker._instance = None
    CeleryHealthChecker._is_initialized = False
    yield
    CeleryHealthChecker._instance = None
    CeleryHealthChecker._is_initialized = False


@pytest.fixture(scope="module")
def running_worker(real_celery_app):
    """Запускаем реальный воркер Celery в фоне для тестов"""
    worker = real_celery_app.Worker(pool='solo', loglevel='INFO')
    thread = threading.Thread(target=worker.start)
    thread.daemon = True
    thread.start()
    # даём воркеру время запуститься
    time.sleep(2)
    yield
    worker.stop()
    thread.join(timeout=5)


@pytest.fixture
def checker(real_celery_app):
    """Создаём чекер без фонового мониторинга"""
    return CeleryHealthChecker.create(
        app=real_celery_app,
        cache_timeout=5,
        inspect_timeout=5,
        monitoring_interval=1
    )


# Test singleton enforcement
def test_singleton_creation_and_get_instance(checker, real_celery_app):
    assert CeleryHealthChecker.get_instance() is checker
    with pytest.raises(RuntimeError):
        CeleryHealthChecker.create(real_celery_app)


def test_check_broker_success(checker):
    assert checker.check_broker() is True


def test_check_backend_success(checker):
    # Если Redis backend доступен, проверка должна пройти
    assert checker.check_backend() is True


def test_check_workers_no_workers(checker):
    # Без запущенных воркеров ping вернёт {} -> False
    assert checker.check_workers() is False


def test_check_workers_with_worker(checker, running_worker):
    assert checker.check_workers() is True


def test_is_healthy_with_worker(checker, running_worker):
    assert checker.is_healthy() is True


def test_is_healthy_uses_cache(checker, monkeypatch):
    calls = []
    monkeypatch.setattr(checker, '_perform_health_check', lambda: calls.append(True) or True)
    # Первый вызов: выполняется проверка
    assert checker.is_healthy() is True
    assert len(calls) == 1
    # Второй вызов: используется кеш
    time.sleep(0.1)
    assert checker.is_healthy() is True
    assert len(calls) == 1


def test_monitoring_thread_updates_cache(real_celery_app):
    checker = CeleryHealthChecker.create(
        app=real_celery_app,
        cache_timeout=1,
        inspect_timeout=1,
        monitoring_interval=0.5
    )
    time.sleep(1)
    status = checker.is_healthy()
    assert isinstance(status, bool)
    checker.stop_monitoring()
