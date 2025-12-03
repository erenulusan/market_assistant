import sqlite3
from pathlib import Path

# Proje kökü -> data/market.db
ROOT = Path(__file__).resolve().parents[1]  # assistant/
DB_PATH = ROOT / "data" / "market.db"


def py_lower(s):
    """ Python'un Unicode destekli lower fonksiyonu """
    if s is None:
        return None
    return s.lower()

def py_trim(s):
    """ Python'un trim fonksiyonu """
    if s is None:
        return None
    return s.strip()

def main():
    conn = sqlite3.connect(DB_PATH)
    

    conn.create_function("PY_LOWER", 1, py_lower)
    conn.create_function("PY_TRIM", 1, py_trim)
    
    cur = conn.cursor()
    print(f"DB path: {DB_PATH}")

    cur.execute(
        """
        UPDATE products
        SET subcategory = PY_LOWER(PY_TRIM(subcategory))
        WHERE subcategory IS NOT NULL;
        """
    )
    print("subcategory alanı PY_LOWER + PY_TRIM ile normalize edildi.")

    # 2) Mapping: ham -> normalize isim
    mapping = {
        "kırmızı et": "Kırmızı Et",
        "beyaz et": "Beyaz Et",
        "balık & deniz ürünleri": "Balık ve Deniz Ürünleri",
        "balık, deniz ürünleri": "Balık ve Deniz Ürünleri",
        "makarnalar": "Makarna",
        "makarna": "Makarna",
        "zeytinyağı": "Zeytinyağı",
        "sıvı yağ": "Sıvı Yağ",
        "sos": "Sos",
        "sirke & salata sosu": "Sos",
        "salça": "Salça",
        "kraker & kurabiye": "Kraker",
        "kraker": "Kraker",
        "tablet çikolata": "Çikolata",
        "çikolata bar": "Bar",
        "bar, kaplamalılar": "Bar",
        "sakız & şekerleme": "Sakız & Şekerleme",
        "sakız": "Sakız & Şekerleme",
        "şekerleme": "Sakız & Şekerleme",
        "su": "Su",
        "gazlı içecek": "Gazlı İçecek",
        "gazsız içecek": "Gazsız İçecek",
        "maden suyu": "Maden Suyu",
        "soğuk çay": "Soğuk Çay",
        "meyve suyu": "Meyve Suyu",
        "enerji içeceği": "Enerji İçeceği",
        "fonksiyonel içecekler": "Fonksiyonel İçecekler",
        "paylaşımlık & draje": "Paylaşımlık & Draje",
        "sürülebilir": "Sürülebilir",
        "tatlı": "Tatlı",
    }

    
    for raw, norm in mapping.items():
        cur.execute(
            """
            UPDATE products
            SET subcategory = ?
            WHERE subcategory = ?;
            """,
            (norm, raw)
        )

    print(f"{len(mapping)} adet mapping UPDATE edildi.")


    conn.commit()
    conn.close()
    print("db bağlantisi kesildi.")


if __name__ == "__main__":
    main()