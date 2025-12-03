from pathlib import Path
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from rich import print

ROOT = Path(__file__).resolve().parents[1]  # project root
DB_PATH = ROOT / "data" / "market.db"

EMB_PATH = ROOT / "data" / "product_embeddings.npy"
ID_PATH = ROOT / "data" / "product_ids.npy"

#db bağlantisi
def get_connection():
    conn= sqlite3.connect(DB_PATH)
    conn.row_factory= sqlite3.Row
    return conn

def fetch_products():
    conn= get_connection()
    cur= conn.cursor()
    cur.execute("""
        SELECT id, norm
        FROM products
        WHERE norm IS NOT NULL AND norm != ''
        ORDER BY id
    """)
    rows= cur.fetchall()
    conn.close()
    return rows

def main():
    rows= fetch_products()
    print(f"[bold red] Toplam ürün sayisi : {len(rows)}[/bold red]")

    texts= [r["norm"] for r in rows] 
    ids= [r["id"] for r in rows] 
    
    #kullanilacak embedding modeli:
    print("Model yükleniyor")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    print("Embedding üretiliyor")
    embeddings= model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings= True, #cosine similarity için
    )
    embeddings= embeddings.astype("float32")

    np.save(EMB_PATH, embeddings)
    np.save(ID_PATH, np.array(ids, dtype="int32"))
    print(f"[Embedding Shape]: {embeddings.shape}")
    print(f"Embeddingler kaydedildi")
    print(f"- [{EMB_PATH}]")
    print(f"- [{ID_PATH}]")


if __name__ == "__main__":
    main()