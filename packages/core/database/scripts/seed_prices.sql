-- ============================================================================
-- СКРИПТ ЗАПОЛНЕНИЯ ТАБЛИЦЫ PRICES
-- Источник: "Отчет EVA по анализу рабочей встречи.pdf"
-- ============================================================================

-- ВАЖНО: Перед запуском убедитесь, что:
-- 1. Таблицы tenants, product_categories, product_options, body_types заполнены
-- 2. У вас есть права на INSERT в таблицу prices

-- ============================================================================
-- EVA-КОВРИКИ (category: eva_mats)
-- ============================================================================

-- Базовые цены EVA-ковриков БЕЗ БОРТОВ (по типам кузова)
INSERT INTO prices (tenant_id, category_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    c.id as category_id,
    bt.id as body_type_id,
    CASE bt.code
        WHEN 'sedan' THEN 2400      -- Седан (без бортов)
        WHEN 'hatchback' THEN 2400  -- Хэтчбек (без бортов)
        WHEN 'suv' THEN 2500         -- Внедорожник (без бортов)
        WHEN 'minivan_small' THEN 6300  -- Маленький минивэн
        WHEN 'minivan_medium' THEN 6500 -- Большой минивэн
        WHEN 'minivan_large' THEN 7000  -- Гигантский минивэн
        WHEN 'truck_single' THEN 2000   -- Грузовые (одна кабина)
        WHEN 'truck_double' THEN 3500   -- Грузовые (двойная кабина)
        ELSE 2400
    END as base_price,
    'KGS' as currency
FROM tenants t
CROSS JOIN product_categories c
CROSS JOIN body_types bt
WHERE t.slug = 'evopoliki'
  AND c.code = 'eva_mats'
  AND bt.code IN ('sedan', 'hatchback', 'suv', 'minivan_small', 'minivan_medium', 'minivan_large', 'truck_single', 'truck_double')
ON CONFLICT DO NOTHING;

-- Опция "С БОРТАМИ" для EVA-ковриков
-- Добавляет +400 сом к базовой цене (седан/хэтчбек) или +500 сом (внедорожник)
INSERT INTO prices (tenant_id, option_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    o.id as option_id,
    bt.id as body_type_id,
    CASE bt.code
        WHEN 'sedan' THEN 400       -- 2400 + 400 = 2800
        WHEN 'hatchback' THEN 400   -- 2400 + 400 = 2800
        WHEN 'suv' THEN 500          -- 2500 + 500 = 3000
        ELSE 400
    END as base_price,
    'KGS' as currency
FROM tenants t
CROSS JOIN product_options o
CROSS JOIN body_types bt
WHERE t.slug = 'evopoliki'
  AND o.slug = 'with_borders'
  AND bt.code IN ('sedan', 'hatchback', 'suv')
ON CONFLICT DO NOTHING;

-- Опция "3-й ряд" для EVA-ковриков (только для внедорожников)
INSERT INTO prices (tenant_id, option_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    o.id as option_id,
    bt.id as body_type_id,
    1000 as base_price,  -- Доп. 3-й ряд (для внедорожников): 1 000 сом
    'KGS' as currency
FROM tenants t
CROSS JOIN product_options o
CROSS JOIN body_types bt
WHERE t.slug = 'evopoliki'
  AND o.slug = 'third_row'
  AND bt.code = 'suv'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 5D-КОВРИКИ (category: 5d_mats)
-- ============================================================================

-- Базовые цены 5D-ковриков (по типам экокожи)
-- Примечание: Эти цены могут быть реализованы через опции или отдельные категории

-- Экокожа "пресс" (2 ряда): 9 000 сом
INSERT INTO prices (tenant_id, category_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    c.id as category_id,
    NULL as body_type_id,  -- Применимо ко всем типам кузова
    9000 as base_price,     -- Базовая цена для экокожи "пресс"
    'KGS' as currency
FROM tenants t
CROSS JOIN product_categories c
WHERE t.slug = 'evopoliki'
  AND c.code = '5d_mats'
ON CONFLICT DO NOTHING;

-- TODO: Добавить опции для разных типов экокожи:
-- - Экокожа со строчкой (2 ряда): 10 500 сом (+1500 к базовой)
-- - Экокожа "крокодил" (2 ряда): 15 000 сом (+6000 к базовой)
-- - Доп. 3-й ряд ("пресс", "строчка"): 5 000 сом
-- - Доп. 3-й ряд ("крокодил"): 7 000 сом
-- - Багажник (любой тип): 6 000 сом

-- ============================================================================
-- АВТОЧЕХЛЫ (category: seat_covers)
-- ============================================================================

-- Ценовой диапазон: 4 000 – 19 000 сом
-- Используем среднюю цену как базовую
INSERT INTO prices (tenant_id, category_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    c.id as category_id,
    NULL as body_type_id,  -- Применимо ко всем типам кузова
    11500 as base_price,   -- Средняя цена: (4000 + 19000) / 2
    'KGS' as currency
FROM tenants t
CROSS JOIN product_categories c
WHERE t.slug = 'evopoliki'
  AND c.code = 'seat_covers'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- НАКИДКИ НА ПАНЕЛЬ (category: dashboard_covers)
-- ============================================================================

-- Ценовой диапазон: 1 800 – 3 000 сом
-- Используем среднюю цену как базовую
INSERT INTO prices (tenant_id, category_id, body_type_id, base_price, currency)
SELECT
    t.id as tenant_id,
    c.id as category_id,
    NULL as body_type_id,  -- Применимо ко всем типам кузова
    2400 as base_price,    -- Средняя цена: (1800 + 3000) / 2
    'KGS' as currency
FROM tenants t
CROSS JOIN product_categories c
WHERE t.slug = 'evopoliki'
  AND c.code = 'dashboard_covers'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- ПРОВЕРКА РЕЗУЛЬТАТОВ
-- ============================================================================

-- Запустите этот запрос, чтобы увидеть все созданные цены:
/*
SELECT
    t.name as tenant,
    c.name_ru as category,
    o.name as option,
    bt.name_ru as body_type,
    p.base_price,
    p.currency
FROM prices p
JOIN tenants t ON p.tenant_id = t.id
LEFT JOIN product_categories c ON p.category_id = c.id
LEFT JOIN product_options o ON p.option_id = o.id
LEFT JOIN body_types bt ON p.body_type_id = bt.id
WHERE t.slug = 'evopoliki'
ORDER BY c.name_ru, bt.name_ru, o.name;
*/

-- ============================================================================
-- ПРИМЕЧАНИЯ
-- ============================================================================

-- 1. Цены взяты из документа "Отчет EVA по анализу рабочей встречи.pdf"
-- 2. Для 5D-ковриков, авточехлов и накидок на панель используются средние цены
--    из диапазона, так как точные цены зависят от дополнительных параметров
-- 3. Для полной реализации ценообразования 5D-ковриков нужно создать
--    дополнительные опции для типов экокожи (пресс, строчка, крокодил)
-- 4. Все цены указаны в сомах (KGS)
