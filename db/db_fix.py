"""
getir scraperinda kategorilerde ilk sub_categoryi için manuel yazmistim o manuelleri elle gireceğim bu script bir kere calistirilacak.

"""
import sqlite3
import os

CURRENT_DIR = os.path.dirname(__file__)
DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "data", "market.db"))

TABLE_NAME = "products" 
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

rules = [
    ("Meyve - Sebze", "Meyve"),
    ("Et - Tavuk - Balık", "kırmızı et"),
    ("Temel Gıda", "sos"),
    ("Atıştırmalık", "Kuruyemiş"),
    ("İçecek", "su"),
]

for top_cat, new_subcat in rules:
    cursor.execute(f"""
        UPDATE {TABLE_NAME}
        SET subcategory = ?
        WHERE site = 'getir'
        AND top_category = ?
        AND subcategory = 'Manuel';
    """, (new_subcat, top_cat))
    print(f" {top_cat} -> manuel -> {new_subcat} güncellendi.")

conn.commit()
conn.close()

print("\n Güncellemeler yapildi!")
