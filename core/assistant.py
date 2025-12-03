# core/assistant.py
from __future__ import annotations
from typing import Dict, Any

from core.product_extractor import extract_shopping_items
from core.recipe_extractor import extract_ingredients
from core.agent_tools import (
    build_item_search_results,
    compute_site_baskets,
    compute_baskets_for_items,
)


def handle_shopping_assistant(query: str, top_n: int = 5) -> Dict[str, Any]:
    """
    Mod: Alışveriş
      - Doğal dil cümleden ürünleri çıkarır (LLM)
      - Her ürün için search_products ile arama yapar
      - Market bazlı sepet + karışık sepet + tasarruf hesabı
    """
    extracted = extract_shopping_items(query)
    items = extracted.get("items", [])

    if not items:
        return {
            "mode": "shopping",
            "query": query,
            "items": [],
            "baskets": {
                "per_site": [],
                "cheapest_single_site": None,
                "best_mix": None,
                "savings": None,
            },
        }

    items_with_results = build_item_search_results(items, top_n=top_n)
    basket_info = compute_site_baskets(items_with_results)

    return {
        "mode": "shopping",
        "query": query,
        "items": items_with_results,
        "baskets": basket_info,
    }


def handle_recipe_assistant(query: str) -> Dict[str, Any]:
    """
    Mod: Tarif malzemesi çıkarma
      - Sadece tarif + malzemeleri döner (market araması yapmaz)
    """
    recipe_data = extract_ingredients(query)

    servings = recipe_data.get("servings")
    recipe_name = recipe_data.get("recipe")
    ingredients_to_buy = recipe_data.get("ingredients_to_buy", [])
    pantry_items = recipe_data.get("pantry_items", [])

    return {
        "mode": "recipe",
        "query": query,
        "recipe": {
            "name": recipe_name,
            "servings": servings,
        },
        "ingredients_to_buy": ingredients_to_buy,
        "pantry_items": pantry_items,
    }


def handle_recipe_to_market(query: str, top_n: int = 5) -> Dict[str, Any]:
    """
    Tek query ile:
      - Tarif malzemelerini çıkar
      - Eksik malzemeler üzerinden market araması yap
      - sepet özetini döndür
    """
    recipe_data = extract_ingredients(query)

    servings = recipe_data.get("servings")
    recipe_name = recipe_data.get("recipe")
    ingredients_to_buy = recipe_data.get("ingredients_to_buy", [])
    pantry_items = recipe_data.get("pantry_items", [])

    items_for_search = []
    for ing in ingredients_to_buy:
        items_for_search.append(
            {
                "name": ing.get("name"),
                "quantity": ing.get("quantity"),
                "unit": None,
                "subcategory": None,
            }
        )

    basket_block = compute_baskets_for_items(items_for_search, top_n=top_n)

    return {
        "mode": "recipe_to_market",
        "query": query,
        "recipe": {
            "name": recipe_name,
            "servings": servings,
        },
        "ingredients_to_buy": ingredients_to_buy,
        "pantry_items": pantry_items,
        "items": basket_block["items"],
        "baskets": basket_block["baskets"],
    }
