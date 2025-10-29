"""
Константы для Telegram-бота EVOPOLIKI.
Содержит популярные марки и модели автомобилей.
"""

# Популярные марки автомобилей (8-10 штук)
POPULAR_BRANDS = [
    "Toyota",
    "Mercedes-Benz",
    "BMW",
    "Lexus",
    "Honda",
    "KIA",
    "Hyundai",
    "Nissan",
    "Volkswagen",
    "Mazda"
]

# Популярные модели для каждой марки (4-5 штук)
# Ключ - название марки, значение - список популярных моделей
POPULAR_MODELS = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander"],
    "Mercedes-Benz": ["E-Class", "C-Class", "S-Class", "GLE", "GLC"],
    "BMW": ["3 Series", "5 Series", "X5", "X3", "7 Series"],
    "Lexus": ["RX", "ES", "NX", "LX", "GX"],
    "Honda": ["Accord", "Civic", "CR-V", "Pilot", "HR-V"],
    "KIA": ["Sportage", "Sorento", "Optima", "Rio", "Seltos"],
    "Hyundai": ["Sonata", "Elantra", "Tucson", "Santa Fe", "Creta"],
    "Nissan": ["Qashqai", "X-Trail", "Patrol", "Murano", "Juke"],
    "Volkswagen": ["Tiguan", "Passat", "Polo", "Jetta", "Touareg"],
    "Mazda": ["CX-5", "Mazda 3", "Mazda 6", "CX-9", "CX-30"]
}

# Callback данные для навигации
CALLBACK_INPUT_BRAND = "input:brand"
CALLBACK_INPUT_MODEL = "input:model"
CALLBACK_BRAND_PREFIX = "brand:"
CALLBACK_MODEL_PREFIX = "model:"
CALLBACK_USE_SUGGESTION = "use_suggestion:"
