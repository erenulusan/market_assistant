from __future__ import annotations
from typing import List, Dict, Any, Optional
import re

from embeddings.search_faiss import search_products


def _clean_search_name(name: str) -> str:
    """
    Arama için ürün adını sadeleştir:
      - Parantez içini at: 'domates (250 gram)' -> 'domates'
      - Sayı içeren token'ları at: '250 gram domates' -> 'domates'
    """
    if not name:
        return ""

    # Parantez içlerini tamamen at
    name = re.sub(r"\([^)]*\)", " ", name)

    # Sayı içeren token'ları at (250, 2.5lt, 1kg vs)
    tokens = name.split()
    filtered_tokens = []
    for tok in tokens:
        if any(ch.isdigit() for ch in tok):
            continue
        filtered_tokens.append(tok)

    cleaned = " ".join(filtered_tokens).strip()

    # Boş kaldıysa fallback olarak orijinal ismin ilk kelimesini kullan
    if not cleaned:
        cleaned = name.strip()

    cleaned = " ".join(cleaned.split())
    return cleaned


def build_item_search_results(items: List[dict], top_n: int) -> List[dict]:
    """
    product_extractor veya recipe_extractor'dan gelen ürün listesi için:
    - her ürün adına göre search_products'i çağır
    - sonuçları item içine göm
    """
    enriched_items: List[dict] = []

    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue

        quantity = item.get("quantity")
        unit = item.get("unit")
        subcat = item.get("subcategory")

        search_name = _clean_search_name(name)

        results_raw = search_products(
            raw_query=search_name,
            top_n=top_n,
            requested_subcategory=subcat,
        )

        enriched_items.append(
            {
                "requested_name": name,
                "search_name": search_name,
                "quantity": quantity,
                "unit": unit,
                "subcategory": subcat,
                "results": results_raw,
            }
        )

    return enriched_items


def compute_site_baskets(items_with_results: List[dict]) -> Dict[str, Any]:
    """
    Her market (site) için:
      - Her ürün için o sitedeki en ucuz adayı seç
      - Tüm ürünlerde aday yoksa o site için sepet oluşturma
    Ayrıca:
      - Karışık sepet: ürün bazında en ucuz
      - Tasarruf hesabı
    """
    # Tüm siteleri topla
    all_sites = set()
    for item in items_with_results:
        for r in item["results"]:
            site = r.get("site")
            if site:
                all_sites.add(site)

    per_site_baskets: List[dict] = []

    # Her site için ayrı sepet
    for site in sorted(all_sites):
        site_items = []
        total_price = 0.0
        valid = True

        for item in items_with_results:
            candidates = [
                r
                for r in item["results"]
                if r.get("site") == site and r.get("price") is not None
            ]

            if not candidates:
                valid = False
                break

            best = min(candidates, key=lambda x: x["price"])
            total_price += float(best["price"])

            site_items.append(
                {
                    "requested_name": item["requested_name"],
                    "search_name": item.get("search_name"),
                    "product_id": best["id"],
                    "product_name": best["name"],
                    "price": best["price"],
                    "site": site,
                }
            )

        if valid:
            per_site_baskets.append(
                {
                    "site": site,
                    "total_price": total_price,
                    "items": site_items,
                }
            )

    # Karışık sepet
    mix_items = []
    mix_total = 0.0
    mix_sites_used = set()
    mix_valid = True

    for item in items_with_results:
        candidates = [r for r in item["results"] if r.get("price") is not None]
        if not candidates:
            mix_valid = False
            break

        best = min(candidates, key=lambda x: x["price"])
        mix_total += float(best["price"])
        mix_sites_used.add(best.get("site"))

        mix_items.append(
            {
                "requested_name": item["requested_name"],
                "search_name": item.get("search_name"),
                "product_id": best["id"],
                "product_name": best["name"],
                "price": best["price"],
                "site": best["site"],
            }
        )

    best_mix: Optional[dict] = None
    if mix_valid and len(mix_sites_used) >= 2:
        best_mix = {
            "total_price": mix_total,
            "items": mix_items,
            "sites_used": sorted(mix_sites_used),
        }

    # En ucuz / en pahalı tek site + tasarruf
    cheapest_single_site: Optional[dict] = None
    savings: Optional[dict] = None

    if per_site_baskets:
        per_site_sorted = sorted(per_site_baskets, key=lambda b: b["total_price"])
        cheapest_single_site = per_site_sorted[0]
        most_expensive_site = per_site_sorted[-1]

        if best_mix is not None:
            savings = {
                "mode": "mixed_vs_cheapest_single_site",
                "amount": cheapest_single_site["total_price"]
                - best_mix["total_price"],
                "cheapest_site": cheapest_single_site["site"],
                "cheapest_total": cheapest_single_site["total_price"],
                "best_mix_total": best_mix["total_price"],
            }
        elif len(per_site_baskets) >= 2:
            savings = {
                "mode": "cheapest_vs_most_expensive_site",
                "amount": most_expensive_site["total_price"]
                - cheapest_single_site["total_price"],
                "cheapest_site": cheapest_single_site["site"],
                "cheapest_total": cheapest_single_site["total_price"],
                "most_expensive_site": most_expensive_site["site"],
                "most_expensive_total": most_expensive_site["total_price"],
            }

    return {
        "per_site": per_site_baskets,
        "best_mix": best_mix,
        "cheapest_single_site": cheapest_single_site,
        "savings": savings,
    }


def compute_baskets_for_items(items_for_search: List[dict], top_n: int = 5) -> dict:
    """
    Halihazırda elimizde item listesi varsa (isim + quantity vs),
    bunun üzerinden direkt market araması + sepet hesabı yapar.
    (ör: recipe_extractor'dan gelen ingredients_to_buy listesi.)
    """
    items_with_results = build_item_search_results(items_for_search, top_n=top_n)
    basket_info = compute_site_baskets(items_with_results)
    return {
        "items": items_with_results,
        "baskets": basket_info,
    }
