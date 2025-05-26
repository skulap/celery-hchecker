import threading
from threading import Lock
from celery import Celery
from celery.backends.base import BaseBackend
from kombu import Connection

from .cache import MemoryCache
import logging


class CeleryHealthChecker:
    _cache_key = 'celery_health_status'

    _lock = Lock()

    _instance = None  # Единственный экземпляр класса
    _is_initialized = False  # Флаг инициализации

    _monitoring_thread = None

    def __init__(
            self,
            *,
            # Если передан уже созданный экземпляр Celery, он будет использован
            app,
            cache_timeout: int = 60,
            inspect_timeout: int = 5,
            monitoring_interval: int = 60,
            backend_check_key: str = 'celery_health_check',
    ):
        if self._is_initialized:
            return

        self._logger = logging.getLogger(self.__class__.__name__)
        self._inspect_timeout = inspect_timeout
        self._backend_check_key = backend_check_key
        self._app: Celery = app
        self._cache = MemoryCache(1000, cache_timeout)

        self._is_initialized = True

        self._monitoring_interval = monitoring_interval
        self._stop_event = threading.Event()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            # Запрещаем создание новых экземпляров, если уже существует
            if cls._instance is not None:
                raise RuntimeError(
                    "Celery health checker has already been initialized. "
                    "Use the get_instance() method to access."
                )
            cls._instance = super().__new__(cls)
            return cls._instance

    @classmethod
    def get_instance(cls):
        """Возвращает существующий экземпляр или None"""
        return cls._instance

    @classmethod
    def create(cls, *args, **kwargs):
        """Создает экземпляр (можно вызвать только один раз)"""
        if cls._instance is not None:
            raise RuntimeError("Celery health checker has already been initialized")
        return cls(*args, **kwargs)

    def check_broker(self) -> bool:
        """Проверка доступности брокера."""
        broker_url = self._app.conf.broker_url
        try:
            with Connection(broker_url) as conn:
                conn.connect()
                conn.release()

            self._logger.debug("Broker connection OK")
            return True
        except Exception as e:
            self._logger.error(f"Broker connection failed: {e}")
            return False

    def check_backend(self) -> bool:
        """Проверка result backend (если настроен)."""
        backend_url = self._app.conf.result_backend
        if not backend_url:
            self._logger.debug("No result_backend configured, skipping")
            return True
        backend: BaseBackend = self._app.backend
        try:
            backend.store_result(self._backend_check_key, 'OK', state='SUCCESS')
            meta = backend.get_task_meta(self._backend_check_key)
            if meta.get('result') != 'OK':
                raise RuntimeError(f"Unexpected backend result: {meta!r}")
            self._logger.debug("Result backend OK")
            return True
        except Exception as e:
            self._logger.error(f"Result backend failed: {e}")
            return False

    def check_workers(self) -> bool:
        """Проверка, что хотя бы один воркер жив и отвечает."""
        try:
            inspector = self._app.control.inspect(timeout=self._inspect_timeout)
            ping = inspector.ping() or {}
            if not ping:
                self._logger.warning("No Celery workers responded to ping")
                return False
            self._logger.debug(f"Workers ping: {ping}")
            return True
        except Exception as e:
            self._logger.error(f"Inspect.ping() error: {e}")
            return False

    def is_healthy(self) -> bool:
        """
        Возвращает статус из кеша или запускает проверку.
        Если внутри воркера — сразу True.
        """
        # Попытаться взять из кеша
        cached_status = self._cache.get(self._cache_key)
        if cached_status is not None:
            self._logger.debug(f"Returning cached status: {cached_status}")
            return cached_status

        status = self._perform_health_check()
        self._cache.set(self._cache_key, status)
        return status

    def _perform_health_check(self) -> bool:
        """Выполняет проверку broker, backend и workers"""
        broker_ok = self.check_broker()
        backend_ok = self.check_backend()
        workers_ok = self.check_workers()
        status = broker_ok and backend_ok and workers_ok
        self._logger.debug(
            f"Health check result broker={broker_ok}, backend={backend_ok}, workers={workers_ok}"
        )
        return status

    def _start_monitoring(self):
        """Запуск фонового мониторинга"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._logger.warning("Celery health check monitoring is already running")
            return

        self._stop_event.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="CeleryHealthMonitor"
        )
        self._monitoring_thread.start()
        self._logger.info("Started periodic health celery health check monitoring")

    def _monitoring_loop(self):
        """Цикл периодической проверки"""
        while not self._stop_event.is_set():
            try:
                status = self._perform_health_check()
                self._cache.set(self._cache_key, status)
                self._logger.debug(f"Celery health check completed. Status: {status}")
            except Exception as e:
                self._logger.error(f"Celery health check monitoring loop error: {str(e)}")

            self._stop_event.wait(self._monitoring_interval)

    def stop_monitoring(self):
        """Остановка мониторинга"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_event.set()
            self._monitoring_thread.join(timeout=5)
            self._logger.info("Celery health check monitoring stopped")

    def __del__(self):
        """Деструктор для корректной остановки"""
        self.stop_monitoring()
