#!/usr/bin/env python3
"""Генерация PDF из CSV и HTML-шаблона (WeasyPrint)."""

from __future__ import annotations

import csv
import os
import re
import sys
import webbrowser
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path


def _ensure_gtk_on_path() -> None:
    """На Windows добавить каталог GTK3 Runtime в PATH (нужен WeasyPrint)."""
    if sys.platform != "win32":
        return
    candidates = [
        Path(r"C:\Program Files\GTK3-Runtime Win64\bin"),
        Path(r"C:\Program Files (x86)\GTK3-Runtime Win64\bin"),
        Path(os.environ.get("GTK_BIN", "")),
    ]
    for bin_dir in candidates:
        if bin_dir and bin_dir.is_dir():
            bin_str = str(bin_dir)
            path = os.environ.get("PATH", "")
            if bin_str not in path:
                os.environ["PATH"] = bin_str + os.pathsep + path
            break


_ensure_gtk_on_path()

try:
    from weasyprint import HTML
except ImportError:
    print(
        "Ошибка: библиотека WeasyPrint не установлена.\n"
        "Установите: pip install weasyprint",
        file=sys.stderr,
    )
    sys.exit(1)
except OSError as exc:
    print(
        "Ошибка: WeasyPrint не может загрузить системные библиотеки "
        "(Pango/GObject/Cairo).\n"
        "Windows: установите GTK3 Runtime\n"
        "  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases\n"
        "macOS: brew install pango gdk-pixbuf libffi\n"
        f"Подробности: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "data.csv"
TEMPLATE_PATH = DATA_DIR / "template.html"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_PDF = OUTPUT_DIR / "report.pdf"

REQUIRED_COLUMNS = ("Товар", "Количество", "Цена")
ROW_START = "<!-- ROW_TEMPLATE_START -->"
ROW_END = "<!-- ROW_TEMPLATE_END -->"


class DataError(Exception):
    """Ошибка в данных CSV или шаблоне."""


def _detect_delimiter(header_line: str) -> str:
    """Определить разделитель по первой строке (заголовку)."""
    # utf-8-sig уже убирает BOM; считаем ; и ,
    if header_line.count(";") >= 2:
        return ";"
    if header_line.count(",") >= 2:
        return ","
    if ";" in header_line:
        return ";"
    return ","


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {path}")

    # utf-8-sig снимает BOM (﻿), который иначе попадает в имя первой колонки
    with path.open(encoding="utf-8-sig", newline="") as fh:
        first_line = fh.readline()
        if not first_line.strip():
            raise DataError("CSV-файл пуст или не содержит заголовков.")
        delimiter = _detect_delimiter(first_line)
        fh.seek(0)
        reader = csv.DictReader(fh, delimiter=delimiter)
        if not reader.fieldnames:
            raise DataError("CSV-файл пуст или не содержит заголовков.")

        fieldnames = [name.strip() for name in reader.fieldnames if name]
        missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
        if missing:
            raise DataError(
                f"В CSV отсутствуют обязательные колонки: {', '.join(missing)}. "
                f"Найдены: {', '.join(fieldnames)}"
            )

        rows: list[dict[str, str]] = []
        for i, raw in enumerate(reader, start=2):
            row = {
                (k.strip() if k else k): (v.strip() if isinstance(v, str) else v)
                for k, v in raw.items()
                if k is not None
            }
            product = row.get("Товар", "")
            qty = row.get("Количество", "")
            price = row.get("Цена", "")

            if not product and not qty and not price:
                continue

            if not product:
                raise DataError(f"Строка {i}: пустое значение в столбце «Товар».")
            if qty == "":
                raise DataError(f"Строка {i}: пустое значение в столбце «Количество».")
            if price == "":
                raise DataError(f"Строка {i}: пустое значение в столбце «Цена».")

            try:
                Decimal(qty.replace(",", "."))
            except InvalidOperation as exc:
                raise DataError(
                    f"Строка {i}: некорректное количество «{qty}»."
                ) from exc

            try:
                Decimal(price.replace(",", "."))
            except InvalidOperation as exc:
                raise DataError(
                    f"Строка {i}: некорректная цена «{price}»."
                ) from exc

            rows.append({"Товар": product, "Количество": qty, "Цена": price})

        if not rows:
            raise DataError("CSV-файл не содержит строк с данными.")
        return rows


def load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"HTML-шаблон не найден: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise DataError(f"HTML-шаблон пуст: {path}")
    if ROW_START not in text or ROW_END not in text:
        raise DataError(
            "В шаблоне не найдены маркеры ROW_TEMPLATE_START / ROW_TEMPLATE_END."
        )
    for placeholder in ("{product}", "{qty}", "{price}", "{itog}"):
        if placeholder not in text:
            raise DataError(f"В шаблоне отсутствует плейсхолдер {placeholder}.")
    return text


def extract_row_template(html: str) -> tuple[str, str, str]:
    pattern = re.compile(
        re.escape(ROW_START) + r"(.*?)" + re.escape(ROW_END),
        re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        raise DataError("Не удалось извлечь шаблон строки таблицы.")
    before = html[: match.start()]
    row_tpl = match.group(1).strip("\n")
    after = html[match.end() :]
    return before, row_tpl, after


def format_number(value: Decimal) -> str:
    # Целое без дроби, иначе 2 знака после запятой
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value:.2f}"


def build_html(template: str, rows: list[dict[str, str]]) -> str:
    before, row_tpl, after = extract_row_template(template)

    rendered_rows: list[str] = []
    total = Decimal("0")

    for row in rows:
        price = Decimal(row["Цена"].replace(",", "."))
        qty_raw = row["Количество"].replace(",", ".")
        qty = Decimal(qty_raw)
        total += price

        rendered_rows.append(
            row_tpl.format(
                product=escape(row["Товар"]),
                qty=escape(format_number(qty)),
                price=escape(format_number(price)),
            )
        )

    body = before + "\n".join(rendered_rows) + after
    return body.replace("{itog}", escape(format_number(total)))


def write_pdf(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(DATA_DIR)).write_pdf(str(output_path))


def open_pdf(path: Path) -> None:
    """Открыть PDF в системной программе / браузере (Windows и macOS)."""
    uri = path.resolve().as_uri()
    webbrowser.open(uri)


def main() -> int:
    try:
        rows = read_csv_rows(CSV_PATH)
        template = load_template(TEMPLATE_PATH)
        html = build_html(template, rows)
        write_pdf(html, OUTPUT_PDF)
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except DataError as exc:
        print(f"Ошибка данных: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Ошибка файловой системы: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — финальный перехват WeasyPrint и пр.
        print(f"Не удалось сформировать PDF: {exc}", file=sys.stderr)
        return 1

    print(f"PDF сохранён: {OUTPUT_PDF}")
    try:
        open_pdf(OUTPUT_PDF)
        print("PDF открыт в программе просмотра.")
    except Exception as exc:  # noqa: BLE001
        print(f"PDF создан, но не удалось открыть автоматически: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
