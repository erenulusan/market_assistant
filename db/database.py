"""
Database baglantisi (sqlite) ve şema olusturmak icin 
bu script bi kere çalistirilcak
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional


class Database:

    def __init__(self, db_name: str = "market.db") -> None:
 
        root = Path(__file__).resolve().parents[1]
        data_dir = root / "data"
        data_dir.mkdir(exist_ok=True)

        self.db_path = data_dir / db_name
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self)-> None:
        self.conn.commit()
        self.conn.close()

    def init_schema(self) -> None:
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT,
                top_category TEXT,
                subcategory TEXT,
                name TEXT,
                price REAL,
                discounted_price REAL
            );
            """
        )
        self.conn.commit()

    def insert_products(self, products: List[Dict[str, Any]]) -> None:
        """
        products: [
          {
            "site": "getir",
            "top_category": "icecek",
            "subcategory": "Maden Suyu",
            "name": "Erikli Su 1.5L",
            "price": 15.9,
            "discounted_price": 13.5
          },
          ...
        ]
        """
        if not products:
            return
        rows= [(
            p.get("site"),
            p.get("top_category"),
            p.get("subcategory"),
            p.get("name"),
            p.get("price"),
            p.get("discounted_price"),
        )
        for p in products
        ]
        self.cursor.executemany(
            """
            INSERT INTO products(site, top_category, subcategory, name, price, discounted_price) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        self.conn.commit()

#calistir

if __name__ =="__main__":
    db=Database()
    db.init_schema()
    print("DATABASE Olusturuldu")
    db.close()
    print("Db bağlantisi kesildi")