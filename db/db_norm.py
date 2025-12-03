"""
embedding icin : top_category + subcategory + name (ürün ismi) ni al
NORM TEXT diye bir sütun olustur ve normalize et.
- Normalize: ASCII dönüşüm, küçük harf, noktalama temizleme
"""

import os
import sqlite3
import re
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
DB_PATH = CURRENT_DIR.parent / "data" / "market.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_text(text: str) -> str:
    if not text:
        return ""

    t = text.lower()

    # türkçe karakterleri ascii'ye çevir
    t = (
        t.replace("ç", "c")
         .replace("ö", "o")
         .replace("ü", "u")
         .replace("ş", "s")
         .replace("ı", "i")
         .replace("ğ", "g")
    )

    # harf + rakam + boşluk dışındaki her şeyi temizle
    t = re.sub(r"[^a-z0-9 ]+", " ", t)

    # fazla boşlukları temizle
    t = " ".join(t.split())

    return t


def ensure_norm_column(cur: sqlite3.Cursor):
    """products tablosunda norm kolonu yoksa ekler."""
    cur.execute("PRAGMA table_info(products)")
    cols = [row[1] for row in cur.fetchall()]
    if "norm" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN norm TEXT;")


def main():
    conn = get_connection()
    cur = conn.cursor()

    #norm kolonu yoksa ekle
    ensure_norm_column(cur)
    conn.commit()

    #  ürünleri çek
    cur.execute("""
        SELECT id, site, top_category, subcategory, name
        FROM products
    """)
    rows = cur.fetchall()

    # her satır için norm hesapla ve yaz
    for r in rows:
        combined = f"{r['top_category']} {r['subcategory']} {r['name']}"
        norm = normalize_text(combined)

        cur.execute(
            "UPDATE products SET norm = ? WHERE id = ?",
            (norm, r["id"])   
        )

    conn.commit()
    conn.close()
    print("Normalizasyon tamam")


if __name__ == "__main__":
    main()
