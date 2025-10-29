"""
Модуль интернационализации (i18n) для мультитенантного бота.
Поддерживает загрузку текстов для разных клиентов и языков.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class I18n:
    """
    Класс для управления локализацией текстов.

    Загружает тексты из JSON файлов в зависимости от:
    - tenant_slug (клиент: evopoliki, five_deluxe)
    - language (язык: ru, ky)
    """

    _instance: Optional['I18n'] = None
    _texts: Dict[str, Any] = {}
    _tenant_slug: Optional[str] = None
    _language: str = "ru"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, tenant_slug: str, language: str = "ru"):
        """
        Инициализирует i18n с указанным клиентом и языком.

        Args:
            tenant_slug: Идентификатор клиента (evopoliki, five_deluxe)
            language: Код языка (ru, ky)
        """
        self._tenant_slug = tenant_slug
        self._language = language
        self._load_texts()

    def _load_texts(self):
        """Загружает тексты из JSON файла."""
        if not self._tenant_slug:
            raise ValueError("tenant_slug not set. Call initialize() first.")

        # Путь к файлу локализации
        locales_dir = Path(__file__).parent / "locales"
        locale_file = locales_dir / self._tenant_slug / f"{self._language}.json"

        if not locale_file.exists():
            raise FileNotFoundError(
                f"Locale file not found: {locale_file}\n"
                f"Please create locales/{self._tenant_slug}/{self._language}.json"
            )

        with open(locale_file, 'r', encoding='utf-8') as f:
            self._texts = json.load(f)

    def set_language(self, language: str):
        """
        Изменяет язык интерфейса.

        Args:
            language: Код языка (ru, ky)
        """
        self._language = language
        self._load_texts()

    def get(self, key: str, **kwargs) -> str:
        """
        Получает текст по ключу с поддержкой вложенных ключей.

        Args:
            key: Ключ текста (может быть вложенным, например "faq.care.question")
            **kwargs: Параметры для форматирования строки

        Returns:
            Локализованный текст

        Examples:
            >>> i18n.get("welcome_message")
            >>> i18n.get("faq.care.question")
            >>> i18n.get("greeting", name="Иван")
        """
        # Поддержка вложенных ключей через точку
        keys = key.split('.')
        value = self._texts

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                break

        if value is None:
            return f"[Missing translation: {key}]"

        # Форматирование строки если есть параметры
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError as e:
                return f"[Format error in {key}: {e}]"

        return value

    def __getattr__(self, name: str) -> Any:
        """
        Позволяет обращаться к текстам как к атрибутам.

        Examples:
            >>> i18n.welcome_message
            >>> i18n.about_us
        """
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        value = self._texts.get(name)
        if value is None:
            return f"[Missing translation: {name}]"
        return value

    @property
    def current_language(self) -> str:
        """Возвращает текущий язык."""
        return self._language

    @property
    def current_tenant(self) -> Optional[str]:
        """Возвращает текущий tenant_slug."""
        return self._tenant_slug


# Глобальный экземпляр i18n
i18n = I18n()


def init_i18n(tenant_slug: str, language: str = "ru"):
    """
    Инициализирует глобальную систему i18n.

    Args:
        tenant_slug: Идентификатор клиента
        language: Код языка по умолчанию
    """
    i18n.initialize(tenant_slug, language)


def get_i18n() -> I18n:
    """Возвращает глобальный экземпляр i18n."""
    return i18n
