# PDFCheck

Генерация PDF-счёта из CSV-данных и HTML-шаблона с помощью **WeasyPrint**.

## Услуга

- Предлагаю готовый скрипт: CSV → аккуратный PDF-счёт.
- Настраиваю под ваш шаблон, брендирование и данные.
- Отдаю `.exe` или `.command` — без установки Python.
- Демо-PDF на ваших данных до оплаты.
- Полезно небольшим магазинам, оптовикам и селлерам маркетплейсов.
- Подходит косметике, стройке, услугам — везде повторяющиеся счета.
- Скорость: счёт за секунды вместо ручного Excel.
- Удобство: один клик — PDF открывается сразу.
- Пакеты: настройка разово, правки по часам, поддержка по подписке.

## Возможности

- Чтение `data/data.csv` (UTF-8, колонки: Товар, Количество, Цена)
- Подстановка строк в таблицу шаблона `data/template.html`
- Расчёт суммы по столбцу «Цена» → плейсхолдер `{itog}`
- Сохранение PDF в `output` и автоматическое открытие
- Корректная кириллица, перенос длинных названий товаров
- Работа на Windows и macOS

## Структура проекта

```
PDFCheck/
├── data/
│   ├── data.csv          # исходные данные
│   └── template.html     # HTML-шаблон
├── output/
│   └── report.pdf        # результат
├── generate_pdf.py       # основной скрипт
├── requirements.txt
└── README.md
```

## Установка

### 1. Python-зависимости

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Системные библиотеки (WeasyPrint)

**Windows:** установите [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)  
(скрипт сам добавит `GTK3-Runtime Win64\bin` в `PATH`).

**macOS:**

```bash
brew install pango gdk-pixbuf libffi
```

## Запуск

```bash
python generate_pdf.py
```

Готовый файл: `output/report.pdf`.

## Формат CSV

Разделитель — `;` или `,`. Пример:

```csv
Товар;Цена;Количество
Крем для лица;1290.00;3
Шампунь;540.50;2
```

## Плейсхолдеры шаблона

| Плейсхолдер | Описание                          |
|-------------|-----------------------------------|
| `{product}` | название товара                   |
| `{qty}`     | количество                        |
| `{price}`   | цена                              |
| `{itog}`    | сумма по столбцу «Цена»           |

Строка таблицы в шаблоне ограничена маркерами `ROW_TEMPLATE_START` / `ROW_TEMPLATE_END`.
