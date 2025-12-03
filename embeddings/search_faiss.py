"""
llm extractorden gelen eğer gelirse subcategoryi search products fonksiyonuna ekle.
"""

from pathlib import Path
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from rich import print
import sys
import faiss
import json
from typing import Optional, List, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.text_utils import normalize_text  # normalize fonksiyonu

DB_PATH = ROOT / "data" / "market.db"
ID_PATH = ROOT / "data" / "product_ids.npy"
INDEX_PATH = ROOT / "data" / "product_index.faiss"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# STOPWORDS (sadece keyword / lexical tarafında) 
STOPWORDS = {
    "almak", "istiyorum", "istiyom", "lütfen", "lutfen",
    "ve", "ile",
    "bir", "iki", "uc", "üç",
    "tane", "adet",
    "litre", "lt", "paket"
}


def strip_stopwords_from_norm(norm_query: str) -> str:
    """
    normalize_text'ten geçmiş cümlenin içinden
    'almak, istiyorum, ve, bir, tane...' gibi kelimeleri atar.

    FAISS tarafında tam cümleyi kullanıyoruz,
    bu fonksiyon sadece:
      - keyword_search
      - lexical_overlap_score girişi için
    kullanılacak.
    """
    tokens = norm_query.split()
    filtered = [t for t in tokens if t not in STOPWORDS]
    if not filtered:
        # Hepsi stopword çıktıysa fallback olarak orijinalini kullan
        return norm_query
    return " ".join(filtered)


def lexical_overlap_score(query_raw: str, product_name_raw: str) -> float:
    """
    query ve ürün adı arasindaki kelime kesisimine göre 0-1 arasi skor üret
    """
    q_norm = normalize_text(query_raw)
    t_norm = normalize_text(product_name_raw)

    q_tokens = set(q_norm.split())
    t_tokens = set(t_norm.split())

    if not q_tokens:
        return 0.0

    common = q_tokens & t_tokens
    return len(common) / len(q_tokens)


def tag_overlap_score(query_raw: str, tags_raw: str | None) -> float:
    """
    query tokenlari ile ürün tagleri arasinda kesisime göre 0-1 arasi skor üret
    tags_raw: JSON string (["makarna", "kuskusk", "pastavilla"]) ya da None
    """

    if not tags_raw:
        return 0.0

    try:
        tags_list = json.loads(tags_raw)
    except Exception:
        return 0.0

    tag_tokens = set()
    for t in tags_list:
        norm_t = normalize_text(str(t))
        if norm_t:
            tag_tokens.update(norm_t.split())

    q_norm = normalize_text(query_raw)
    q_tokens = set(q_norm.split())

    if not q_tokens or not tag_tokens:
        return 0.0

    common = q_tokens & tag_tokens
    return len(common) / len(q_tokens)


def keyword_search(
    cur,
    norm_query: str,
    limit: int = 100,
    requested_subcategory: Optional[str] = None,  # <-- YENİ
):
    """
    norm kolonu üzerinden LIKE araması
    - norm_query: normalize_text'ten geçti
    - tüm tokenların geçmesini iste (AND)
    - varsa requested_subcategory ile filtrele
    """
    # Stopword'leri atılmış versiyon
    norm_query = strip_stopwords_from_norm(norm_query)

    tokens = norm_query.split()
    if not tokens:
        return []

    sql = """
    SELECT id, site, name, price, discounted_price,
           COALESCE(discounted_price, price) as effective_price,
           subcategory, tags
    FROM products
    WHERE norm IS NOT NULL
    """

    params: List = []

    # subcategory varsa filtrele
    if requested_subcategory:
        sql += " AND LOWER(TRIM(subcategory)) = LOWER(TRIM(?)) "
        params.append(requested_subcategory)

    # token bazlı AND LIKE
    for t in tokens:
        sql += " AND norm LIKE ? "
        params.append(f"%{t}%")

    sql += " LIMIT ? "
    params.append(limit)

    cur.execute(sql, params)
    return cur.fetchall()


# GLOBAL tek seferlik yüklenen objects
_model: SentenceTransformer | None = None
_index = None
_product_ids: np.ndarray | None = None


def _load_search_artifacts():
    """ model + faiss + id listi sadece ilk çağrida yükle """
    global _model, _index, _product_ids

    if _model is None:
        print("[bold yellow] Sentence transformer modeli loading... [/bold yellow]")
        _model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

    if _index is None or _product_ids is None:
        print("[bold yellow] FAISS index ve product ids loading... [/bold yellow]")
        _index = faiss.read_index(str(INDEX_PATH))
        _product_ids = np.load(ID_PATH)


# arama fonksiyonu
def search_products(
    raw_query: str,
    top_n: int = 10,
    requested_subcategory: Optional[str] = None,
) -> List[Dict]:
    _load_search_artifacts()

    norm_query = normalize_text(raw_query)
    if not norm_query:
        return []

    conn = get_connection()
    cur = conn.cursor()

    K_SEMANTIC = 50
    LEXICAL_WEIGHT = 0.3
    TAG_WEIGHT = 0.5
    KEYWORD_BONUS = 0.4
    SUBCAT_BONUS = 0.30

    # keyword search (artık subcategory'i de kullanıyoruz)
    keyword_rows = keyword_search(
        cur,
        norm_query,
        limit=100,
        requested_subcategory=requested_subcategory,
    )
    has_keyword_hits = len(keyword_rows) > 0

    # semantic arama (FAISS) -> burada FULL cümle (stopwords dahil) kullan
    query_vec = _model.encode(
        [norm_query],
        normalize_embeddings=True,
    ).astype("float32")

    D, I = _index.search(query_vec, K_SEMANTIC)
    faiss_indices = I[0]
    faiss_sims = D[0]

    candidates: Dict[int, Dict] = {}

    # semantic sonuçları ekle
    for idx, sim in zip(faiss_indices, faiss_sims):
        if idx == -1:
            continue

        db_id = int(_product_ids[idx])

        cur.execute(
            """
            SELECT id, site, name, price, discounted_price,
                   COALESCE(discounted_price, price) AS effective_price,
                   subcategory, tags 
            FROM products 
            WHERE id = ?
            """,
            (db_id,),
        )
        row = cur.fetchone()
        if not row:
            continue

        candidates[db_id] = {
            "id": row["id"],
            "site": row["site"],
            "name": row["name"],
            "price": row["effective_price"],
            "original_price": row["price"],
            "discounted_price": row["discounted_price"],
            "subcategory": row["subcategory"],
            "tags": row["tags"],
            "semantic_score": float(sim),
            "keyword_hit": False,
        }

    # keyword sonuçları ekle
    for row in keyword_rows:
        db_id = row["id"]
        if db_id in candidates:
            candidates[db_id]["keyword_hit"] = True
        else:
            candidates[db_id] = {
                "id": row["id"],
                "site": row["site"],
                "name": row["name"],
                "price": row["effective_price"],
                "original_price": row["price"],
                "discounted_price": row["discounted_price"],
                "subcategory": row["subcategory"],
                "tags": row["tags"],
                "semantic_score": 0.0,
                "keyword_hit": True,
            }

    if not candidates:
        conn.close()
        return []

    scored: List[Dict] = []

    # lexical tarafında da stopword'leri filtreden geçmiş query kullan
    lex_query_for_overlap = strip_stopwords_from_norm(norm_query)

    for item in candidates.values():
        lex_score = lexical_overlap_score(lex_query_for_overlap, item["name"])
        tag_score = tag_overlap_score(raw_query, item["tags"])
        semantic_score = item["semantic_score"]
        keyword_bonus = KEYWORD_BONUS if item["keyword_hit"] else 0.0

        # SUBCATEGORY BONUS
        subcat_bonus = 0.0
        if requested_subcategory and item["subcategory"]:
            if item["subcategory"].strip().lower() == requested_subcategory.strip().lower():
                subcat_bonus = SUBCAT_BONUS

        final_score = (
            semantic_score
            + LEXICAL_WEIGHT * lex_score
            + TAG_WEIGHT * tag_score
            + keyword_bonus
            + subcat_bonus
        )

        scored.append(
            {
                **item,
                "lexical_score": lex_score,
                "tag_score": tag_score,
                "final_score": final_score,
            }
        )

    # keyword match varsa alakasızları temizle
    if has_keyword_hits:
        scored = [
            x
            for x in scored
            if x["keyword_hit"] or x["lexical_score"] > 0 or x["tag_score"] > 0
        ]

    if not scored:
        conn.close()
        return []

    scored.sort(key=lambda x: x["final_score"], reverse=True)

    conn.close()
    return scored[:top_n]


# terminalde test
def main():
    print("[bold green] başlatılıyor... [/bold green]")
    _load_search_artifacts()
    print("[bold yellow] arama motoru hazir [/bold yellow]")
    print("çıkmak için 'q' tusuna bas")

    while True:
        raw_query = input("\n Aranilan ürün: ").strip()
        if raw_query.lower() == "q":
            print("Arama bitti")
            break

        results = search_products(raw_query, top_n=10)
        if not results:
            print("[bold red] hic ürün yok [/bold red]")
            continue

        print(f"\n '[bold]{raw_query}[/bold]' için sonuçlar:\n")
        for i, item in enumerate(results, start=1):
            price_str = (
                f"{item['price']} TL" if item["price"] is not None else "Fiyat Yok"
            )

            sem_pct = item["semantic_score"] * 100
            lex_pct = item["lexical_score"] * 100
            tag_pct = item["tag_score"] * 100
            final_pct = item["final_score"] * 100

            print(f"- {i}. [{final_pct:.1f}%] {item['name']}")
            print(
                f"- {item['site'].upper()} |  {price_str} |  {item['subcategory']}"
            )
            print(
                f"- (semantic: {sem_pct:.1f} | lexical: {lex_pct:.1f} | tag: {tag_pct:.1f} | keyword_hit: {item.get('keyword_hit', False)})"
            )
            print("      ------------------------------------------")

    print("database bağlantisi kesildi")


if __name__ == "__main__":
    main()
