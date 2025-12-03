from typing import Optional, List
from pathlib import Path
import sqlite3
import sys

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "market.db"
sys.path.append(str(ROOT))

from core.assistant import (
    handle_shopping_assistant,
    handle_recipe_assistant,
    handle_recipe_to_market,   
)

from agent import agent_reply 


# DB bağlantısı
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Pydantic modeller
class Product(BaseModel):
    id: int
    site: str
    top_category: str
    subcategory: str
    name: str
    price: Optional[float] = None
    discounted_price: Optional[float] = None


# Sepet analizi modelleri
class BasketItemIn(BaseModel):
    product_id: int
    quantity: float = 1.0


class BasketItemOut(BaseModel):
    product_id: int
    name: str
    site: str
    unit_price: float
    quantity: float
    line_total: float


class BasketSiteBreakdown(BaseModel):
    site: str
    total: float
    items: List[BasketItemOut]


class BasketAnalyzeRequest(BaseModel):
    items: List[BasketItemIn]


class BasketAnalyzeResponse(BaseModel):
    items: List[BasketItemOut]
    per_site: List[BasketSiteBreakdown]
    overall_total: float
    summary_text: str

class AgentChatRequest(BaseModel):
    text:str

# FastAPI app
app = FastAPI(title="Market Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # geliştirme için serbest
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}


# Ürün listeleme (debug / filtreli liste)
@app.get("/products", response_model=List[Product])
def list_products(
    site: Optional[str] = Query(None, description="migros / getir"),
    top_category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    q: Optional[str] = Query(None, description="İsim içinde arama"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Products tablosundan filtreli liste döndür:
      - site, top_category, subcategory ile filtreleme
      - min_price - max_price
      - q: name LIKE '%q%'
    """
    base_query = """
        SELECT id, site, top_category, subcategory, name, price, discounted_price
        FROM products
        WHERE 1 = 1
    """

    params: list = []

    if site:
        base_query += " AND site = ?"
        params.append(site)

    if top_category:
        base_query += " AND top_category = ?"
        params.append(top_category)

    if subcategory:
        base_query += " AND subcategory = ?"
        params.append(subcategory)

    if min_price is not None:
        base_query += " AND COALESCE(discounted_price, price) >= ?"
        params.append(min_price)

    if max_price is not None:
        base_query += " AND COALESCE(discounted_price, price) <= ?"
        params.append(max_price)

    if q:
        q_norm = q.strip().lower()
        base_query += " AND (' ' || LOWER(name) || ' ') LIKE ?"
        params.append(f"% {q_norm} %")

    base_query += " ORDER BY site, top_category, subcategory, name"
    base_query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(base_query, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    products = [Product(**dict(row)) for row in rows]
    return products


# Alışveriş asistanı (direkt alışveriş cümlesi)
@app.get("/assistant/shopping-full")
def shopping_full(
    q: str = Query(..., description="Doğal dil alışveriş cümlesi"),
    k: int = Query(
        5,
        ge=1,
        le=20,
        description="Her ürün için maksimum döndürülecek sonuç sayısı",
    ),
):
    """
    Full alışveriş asistanı:
      - LLM ürünleri parse eder
      - search_products ile arama yapar
      - market bazlı sepetleri ve karışık sepeti hesaplar
      - tasarruf bilgisini de döner

    Dönüş formatı core.assistant.handle_shopping_assistant ile aynı (dict).
    """
    out = handle_shopping_assistant(q, top_n=k)
    return out


# Tarif asistanı (sadece malzeme listesi)
@app.get("/recipe/ingredients")
def recipe_ingredients(
    q: str = Query(..., description="Ne pişirmek istiyorsun? (örn: domates çorbası)"),
):
    """
    Tarif asistanı:
      - core.assistant.handle_recipe_assistant çağırır
      - Tarif adı, kişi sayısı, ingredients_to_buy, pantry_items döner
    """
    out = handle_recipe_assistant(q)
    return out


# Tarif -> Market (tek adımda sepet önerisi)
@app.get("/assistant/recipe-to-market")
def recipe_to_market(
    q: str = Query(..., description="Ne pişirmek istiyorsun?"),
    k: int = Query(
        5,
        ge=1,
        le=20,
        description="Her malzeme için maksimum döndürülecek sonuç sayısı",
    ),
):
    """
    Tek bir endpoint ile:
      - Tarif malzemelerini çıkarır
      - Eksik malzemeler üzerinden market araması yapar
      - sepet özetini döner

    Dönüş formatı core.assistant.handle_recipe_to_market ile aynı (dict).
    """
    out = handle_recipe_to_market(q, top_n=k)
    return out


# Sepet analizi
@app.post("/basket/analyze", response_model=BasketAnalyzeResponse)
def analyze_basket(payload: BasketAnalyzeRequest):
    """
    Body örneği:
    {
      "items": [
        { "product_id": 3811, "quantity": 1 },
        { "product_id": 679,  "quantity": 2 }
      ]
    }

    - product_id'lere göre ürünleri DB'den çeker
    - Site bazlı toplamları hesaplar
    - Genel toplam ve açıklayıcı bir summary_text üretir
    """
    if not payload.items:
        return BasketAnalyzeResponse(
            items=[],
            per_site=[],
            overall_total=0.0,
            summary_text="Sepet boş görünüyor. Önce ürün eklemelisin.",
        )

    product_ids = [item.product_id for item in payload.items]

    # Dinamik IN (...) sorgusu
    placeholders = ",".join(["?"] * len(product_ids))
    query = f"""
        SELECT id, site, name,
               COALESCE(discounted_price, price) AS effective_price
        FROM products
        WHERE id IN ({placeholders})
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, product_ids)
        rows = cur.fetchall()
    finally:
        conn.close()

    # DB'den gelen ürünleri dict'e maple
    products_by_id = {
        row["id"]: {
            "id": row["id"],
            "site": row["site"],
            "name": row["name"],
            "unit_price": float(row["effective_price"])
            if row["effective_price"] is not None
            else 0.0,
        }
        for row in rows
    }

    # Tek tek satırları (BasketItemOut) üret
    items_out: List[BasketItemOut] = []
    per_site_map: dict[str, List[BasketItemOut]] = {}

    for item in payload.items:
        prod = products_by_id.get(item.product_id)
        if not prod:
            # Ürün DB'de yoksa atlıyoruz
            continue

        unit_price = prod["unit_price"]
        line_total = unit_price * item.quantity

        out_item = BasketItemOut(
            product_id=prod["id"],
            name=prod["name"],
            site=prod["site"],
            unit_price=unit_price,
            quantity=item.quantity,
            line_total=line_total,
        )

        items_out.append(out_item)
        per_site_map.setdefault(prod["site"], []).append(out_item)

    # Site bazlı breakdown
    per_site: List[BasketSiteBreakdown] = []
    overall_total = 0.0

    for site, site_items in per_site_map.items():
        site_total = sum(i.line_total for i in site_items)
        overall_total += site_total
        per_site.append(
            BasketSiteBreakdown(
                site=site,
                total=site_total,
                items=site_items,
            )
        )

    # Summary text
    if not items_out:
        summary = "Sepetteki ürünlerin hiçbiri veritabanında bulunamadı."
    else:
        summary_lines: List[str] = []
        summary_lines.append(f"Sepetinde toplam {len(items_out)} satır ürün var.\n")

        # Site bazlı detay
        for site_block in per_site:
            summary_lines.append(f"{site_block.site} için toplam: {site_block.total:.2f} TL")
            for it in site_block.items:
                summary_lines.append(
                    f"  - {it.name} x{it.quantity} → {it.line_total:.2f} TL"
                )
            summary_lines.append("")  # boş satır

        summary_lines.append(f"Genel toplam: {overall_total:.2f} TL")

        if len(per_site) >= 2:
            # En ucuz ve en pahalı siteyi kıyasla
            sorted_sites = sorted(per_site, key=lambda s: s.total)
            cheapest = sorted_sites[0]
            most_expensive = sorted_sites[-1]
            diff = most_expensive.total - cheapest.total
            if diff > 0:
                summary_lines.append(
                    f"Aynı sepeti en ucuz site olan {cheapest.site} yerine "
                    f"{most_expensive.site} üzerinden alsaydın yaklaşık {diff:.2f} TL fazla öderdın."
                )

        summary = "\n".join(summary_lines)

    return BasketAnalyzeResponse(
        items=items_out,
        per_site=per_site,
        overall_total=overall_total,
        summary_text=summary,
    )

#main agent
@app.get("/assistant/agent")
def assistant_agent(q: str):
    """
    Genel agent endpoint:
    - agent.agent_reply(q) döner
    """
    return agent_reply(q)