"""
SQLAlchemy модели для мульти-арендной SaaS платформы чат-ботов.

Этот модуль содержит все модели данных для системы автоматизации
продаж автомобильных аксессуаров через чат-боты.

Ключевые особенности:
- Row-level multitenancy через tenant_id
- Нормализованная структура для избежания дублирования данных
- Гибкое ценообразование с поддержкой множественных арендаторов
- Полная типизация для type checking

Author: Claude
Date: 2025-01-09
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DECIMAL,
    ForeignKey, DateTime, JSON, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# ============================================================================
# CORE TABLES - Ядро системы
# ============================================================================

class Tenant(Base):
    """
    Арендатор (клиент SaaS-платформы).

    Каждый tenant представляет отдельную компанию, использующую платформу.
    Все данные (цены, лекала, тексты) строго изолированы по tenant_id.

    Примеры: evopoliki, five_deluxe
    """
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # JSONB поля для гибкого хранения настроек
    contacts: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # {"phone": "+996...", "address": "..."}
    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # конфигурация бота

    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    patterns: Mapped[List["Pattern"]] = relationship("Pattern", back_populates="tenant", cascade="all, delete-orphan")
    prices: Mapped[List["Price"]] = relationship("Price", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"


# ============================================================================
# VEHICLE REFERENCE TABLES - Справочники автомобилей
# ============================================================================

class Brand(Base):
    """
    Марка автомобиля (Toyota, Honda, BMW и т.д.).

    Глобальный справочник, используется всеми арендаторами.
    """
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(100))
    name_kg: Mapped[Optional[str]] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    models: Mapped[List["Model"]] = relationship("Model", back_populates="brand", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Brand(id={self.id}, name='{self.name}')>"


class BodyType(Base):
    """
    Тип кузова автомобиля.

    Возможные значения: sedan, hatchback, suv, minivan, truck
    Используется для определения базовой цены и применимости опций.
    """
    __tablename__ = "body_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_kg: Mapped[Optional[str]] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    models: Mapped[List["Model"]] = relationship("Model", back_populates="body_type")
    prices: Mapped[List["Price"]] = relationship("Price", back_populates="body_type")

    def __repr__(self) -> str:
        return f"<BodyType(code='{self.code}', name_ru='{self.name_ru}')>"


class Model(Base):
    """
    Модель автомобиля.

    Связывает марку, название модели, годы выпуска и тип кузова.
    Пример: Toyota Camry 2018-2023, тип кузова: Седан
    """
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(Integer, ForeignKey("brands.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(100))

    year_from: Mapped[Optional[int]] = mapped_column(Integer)
    year_to: Mapped[Optional[int]] = mapped_column(Integer)

    body_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("body_types.id"))

    # JSONB для дополнительных характеристик
    model_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)  # {"steering": "left", "generation": "XV70"}

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="models")
    body_type: Mapped[Optional["BodyType"]] = relationship("BodyType", back_populates="models")
    patterns: Mapped[List["Pattern"]] = relationship("Pattern", back_populates="model")

    __table_args__ = (
        UniqueConstraint('brand_id', 'name', 'year_from', 'year_to', name='uq_model_brand_name_years'),
        Index('idx_models_brand', 'brand_id'),
        Index('idx_models_body_type', 'body_type_id'),
    )

    def __repr__(self) -> str:
        return f"<Model(id={self.id}, brand={self.brand.name if self.brand else 'N/A'}, name='{self.name}')>"


# ============================================================================
# PRODUCT TABLES - Продукты и опции
# ============================================================================

class ProductCategory(Base):
    """
    Категория товара.

    Примеры: EVA-коврики, Автомобильные чехлы, 5D-коврики, Накидки на панель
    """
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    name_kg: Mapped[Optional[str]] = mapped_column(String(255))

    description_ru: Mapped[Optional[str]] = mapped_column(Text)
    description_kg: Mapped[Optional[str]] = mapped_column(Text)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    options: Mapped[List["ProductOption"]] = relationship("ProductOption", back_populates="category", cascade="all, delete-orphan")
    patterns: Mapped[List["Pattern"]] = relationship("Pattern", back_populates="category")
    prices: Mapped[List["Price"]] = relationship("Price", back_populates="category")

    def __repr__(self) -> str:
        return f"<ProductCategory(code='{self.code}', name_ru='{self.name_ru}')>"


class ProductOption(Base):
    """
    Опция товара (модификатор стоимости или комплектации).

    Примеры:
    - С бортами / Без бортов
    - 3-й ряд
    - Багажник
    - Тип экокожи: ["пресс", "строчка", "крокодил"]

    Типы опций:
    - boolean: Да/Нет (например, "с бортами")
    - choice: Выбор из списка (например, тип экокожи)
    - addon: Дополнительная опция (например, 3-й ряд)
    """
    __tablename__ = "product_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    name_kg: Mapped[Optional[str]] = mapped_column(String(255))

    # Тип опции: boolean, choice, addon
    option_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Для choice: список допустимых значений
    allowed_values: Mapped[Optional[List[str]]] = mapped_column(JSON)  # ["пресс", "строчка", "крокодил"]

    # К каким типам кузова применима опция
    applicable_to: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # {"body_types": ["suv", "minivan"]}

    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    category: Mapped["ProductCategory"] = relationship("ProductCategory", back_populates="options")
    prices: Mapped[List["Price"]] = relationship("Price", back_populates="option")

    __table_args__ = (
        UniqueConstraint('category_id', 'code', name='uq_option_category_code'),
        Index('idx_options_category', 'category_id'),
    )

    def __repr__(self) -> str:
        return f"<ProductOption(code='{self.code}', name_ru='{self.name_ru}', type='{self.option_type}')>"


# ============================================================================
# BUSINESS LOGIC TABLES - Бизнес-логика
# ============================================================================

class Pattern(Base):
    """
    Лекало (выкройка) - наличие возможности изготовления аксессуара.

    Определяет, может ли конкретный арендатор изготовить товар
    для определенной модели автомобиля.

    Ключ изоляции: tenant_id
    """
    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Мульти-арендность
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)

    available: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Из Excel: "с бортами правый руль", "полный салон"

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="patterns")
    category: Mapped["ProductCategory"] = relationship("ProductCategory", back_populates="patterns")
    model: Mapped["Model"] = relationship("Model", back_populates="patterns")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'category_id', 'model_id', name='uq_pattern_tenant_category_model'),
        Index('idx_patterns_tenant', 'tenant_id'),
        Index('idx_patterns_model', 'model_id'),
        Index('idx_patterns_lookup', 'tenant_id', 'category_id', 'model_id'),
    )

    def __repr__(self) -> str:
        return f"<Pattern(tenant_id={self.tenant_id}, category_id={self.category_id}, model_id={self.model_id}, available={self.available})>"


class Price(Base):
    """
    Цена товара или опции.

    Гибкая система ценообразования:
    - Каждый арендатор может иметь свои цены
    - Цены могут зависеть от типа кузова
    - Поддержка временных рамок действия цены

    Ключ изоляции: tenant_id

    Правила:
    - Либо category_id, либо option_id (не оба сразу)
    - body_type_id опциональный (null = применимо ко всем)
    """
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Мульти-арендность
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Либо базовая цена категории, либо цена опции
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("product_categories.id", ondelete="CASCADE"))
    option_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("product_options.id", ondelete="CASCADE"))

    # Для какого типа кузова (null = для всех)
    body_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("body_types.id", ondelete="CASCADE"))

    base_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default='KGS')

    # Временные рамки действия цены
    valid_from: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="prices")
    category: Mapped[Optional["ProductCategory"]] = relationship("ProductCategory", back_populates="prices")
    option: Mapped[Optional["ProductOption"]] = relationship("ProductOption", back_populates="prices")
    body_type: Mapped[Optional["BodyType"]] = relationship("BodyType", back_populates="prices")

    __table_args__ = (
        CheckConstraint(
            '(category_id IS NOT NULL AND option_id IS NULL) OR (category_id IS NULL AND option_id IS NOT NULL)',
            name='chk_price_category_or_option'
        ),
        Index('idx_prices_tenant', 'tenant_id'),
        Index('idx_prices_category', 'category_id'),
        Index('idx_prices_option', 'option_id'),
        Index('idx_prices_validity', 'valid_from', 'valid_to', postgresql_where='valid_to IS NULL'),
    )

    def __repr__(self) -> str:
        return f"<Price(tenant_id={self.tenant_id}, price={self.base_price} {self.currency})>"


class Application(Base):
    """
    Заявка клиента.

    Хранит все заявки от клиентов для обработки менеджерами.
    Каждая заявка привязана к арендатору и содержит полную
    информацию о заказе и контактных данных клиента.

    Ключ изоляции: tenant_id

    Статусы:
    - new: Новая заявка, ожидает обработки
    - in_progress: Заявка взята в работу менеджером
    - completed: Заявка обработана
    - cancelled: Заявка отменена
    """
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Мульти-арендность
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Информация о клиенте
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Telegram ID
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_username: Mapped[Optional[str]] = mapped_column(String(100))  # Telegram username

    # Детали заявки в JSON
    application_details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Пример: {
    #   "brand_name": "Toyota",
    #   "model_name": "Camry",
    #   "category_name": "EVA-коврики",
    #   "option_details": "С бортами",
    #   "total_price": 5000,
    #   "is_individual_measure": false
    # }

    # Статус и обработка
    status: Mapped[str] = mapped_column(String(20), default='new', nullable=False, index=True)
    manager_id: Mapped[Optional[int]] = mapped_column(Integer)  # Telegram ID менеджера
    manager_username: Mapped[Optional[str]] = mapped_column(String(100))  # Telegram username менеджера

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")

    __table_args__ = (
        Index('idx_applications_tenant', 'tenant_id'),
        Index('idx_applications_customer', 'customer_id'),
        Index('idx_applications_status', 'status'),
        Index('idx_applications_created', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, customer='{self.customer_name}', status='{self.status}')>"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_models() -> list[type[Base]]:
    """Возвращает список всех моделей для использования в миграциях и тестах."""
    return [
        Tenant,
        Brand,
        BodyType,
        Model,
        ProductCategory,
        ProductOption,
        Pattern,
        Price,
        Application,
    ]


def get_tenant_scoped_models() -> list[type[Base]]:
    """Возвращает список моделей с tenant_id для настройки RLS."""
    return [Pattern, Price, Application]


if __name__ == "__main__":
    # Для быстрой проверки структуры
    print("Доступные модели:")
    for model in get_all_models():
        print(f"  - {model.__tablename__}: {model.__doc__.split('.')[0] if model.__doc__ else 'N/A'}")
