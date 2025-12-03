from __future__ import annotations
from typing import Dict, Any

from core.agent_mod_classifier import classify_mode

from core.product_extractor import extract_shopping_items
from core.recipe_extractor import extract_ingredients
from core.agent_tools import (
    build_item_search_results,
    compute_site_baskets,
    compute_baskets_for_items,
)


SESSION = {
    "last_recipe": None,
    "awaiting_recipe_flow": False,
}


# Basit heuristik mode tahmini
def _heuristic_mode_detect(user_input: str) -> str | None:
    """
    LLM kafayı yerse bile Türkçe pattern'lerden mode tahmini yap.
    - Öncelik: net recipe / net shopping cümlelerini yakalamak.
    - Döner: "shopping", "recipe" veya None
    """
    text = user_input.lower().strip()

    text = text.replace("ı", "i").replace("İ", "i")

    # Recipe vibe: yapmak istiyorum, pisirmek, tarif, yemek...
    recipe_keywords = [
        "yapmak istiyorum",
        "yapicam",
        "yapıyorum",
        "pisirmek istiyorum",
        "pişirmek istiyorum",
        "tarif",
        "yemek yapmak",
        "makarna yapmak",
        "köfte yapmak",
        "corbasi yapmak",
        "çorbası yapmak",
    ]

    # Shopping vibe: almak, alacagim, market, sepete...
    shopping_keywords = [
        "almak istiyorum",
        "alacagim",
        "alacağım",
        "alirim",
        "marketten",
        "alisveris",
        "alışveriş",
        "sepete ekle",
        "sepete at",
        "satın al",
        "satin al",
    ]

    # Eğer cümlede "yapmak istiyorum" geçiyorsa ama "almak" vs yoksa → recipe
    if any(kw in text for kw in recipe_keywords):
        if not any(kw in text for kw in shopping_keywords):
            return "recipe"

    # Eğer cümlede net alışveriş kelimeleri varsa → shopping
    if any(kw in text for kw in shopping_keywords):
        return "shopping"

    # "yemek yapmak istiyoru" gibi typo'lar için:
    if "yemek" in text and "yap" in text:
        return "recipe"

    # Hiçbiri değilse None
    return None


def handle_shopping(query: str) -> dict:
    extracted = extract_shopping_items(query)
    items = extracted.get("items", [])

    if not items:
        return {
            "mode": "shopping",
            "message": "Herhangi bir ürün bulamadım.",
            "items": [],
            "baskets": {},
        }

    # FAISS aramaları + sepet hesapları
    items_with_results = build_item_search_results(items, top_n=5)
    basket_info = compute_site_baskets(items_with_results)

    return {
        "mode": "shopping",
        "query": query,
        "items": items_with_results,
        "baskets": basket_info,
    }


def handle_recipe(query: str) -> dict:
    recipe_data = extract_ingredients(query)

    # Global state güncellenir
    SESSION["last_recipe"] = recipe_data
    SESSION["awaiting_recipe_flow"] = True

    return {
        "mode": "recipe",
        "message": (
            "Bu yemek için malzemeleri çıkardım. "
            "İstersen senin için tarif verebilirim ya da market araması yapabilirim."
        ),
        "recipe": {
            "name": recipe_data.get("recipe"),
            "servings": recipe_data.get("servings"),
        },
        "ingredients_to_buy": recipe_data.get("ingredients_to_buy", []),
        "pantry_items": recipe_data.get("pantry_items", []),
    }


def handle_recipe_flow(user_input: str) -> dict:
    last_recipe = SESSION.get("last_recipe")
    if not last_recipe:
        return {
            "mode": "recipe_flow_continue",
            "message": "Önce bir yemek söylemen gerekiyor :)",
        }

    text = user_input.lower()

    if "tarif" in text or "nasıl yapılır" in text or "yapılışı" in text:
        name = last_recipe.get("recipe", "Bu yemek")

        recipe_text = (
            f"{name} için basit bir tarif istersen şu şekilde yapabilirsin:\n\n"
            "1) Malzemeleri hazırla.\n"
            "2) Ocağı orta ateşte aç.\n"
            "3) Malzemeleri sırayla ekleyerek pişir.\n"
            "4) Damak tadına göre tuz/baharat ayarla.\n\n"
            "Bu kısmı sonra detaylandırabiliriz."
        )

        SESSION["awaiting_recipe_flow"] = False

        return {
            "mode": "recipe_flow_continue",
            "action": "give_recipe",
            "recipe_steps": recipe_text,
        }

    if "market" in text or "ucuz" in text or "sepete" in text or "arama" in text:
        ingredients = last_recipe.get("ingredients_to_buy", [])

        items_for_search = []
        for ing in ingredients:
            items_for_search.append(
                {
                    "name": ing["name"],
                    "quantity": ing["quantity"],
                    "unit": None,
                    "subcategory": None,
                }
            )

        search_block = compute_baskets_for_items(items_for_search, top_n=5)

        SESSION["awaiting_recipe_flow"] = False

        return {
            "mode": "recipe_flow_continue",
            "action": "market_search",
            "items": search_block["items"],
            "baskets": search_block["baskets"],
        }

    # Kullanıcı hala net değilse
    return {
        "mode": "recipe_flow_continue",
        "message": "Ne yapmamı istersin? Tarif mi vereyim yoksa market araması mı yapayım?",
    }


# AGENT ANA FONKSİYON
def agent_reply(user_input: str) -> dict:
    """
    Tüm routing burada.
    """
    #  Eğer zaten tarif flow'undayız → direkt oraya
    if SESSION["awaiting_recipe_flow"]:
        print("[DEBUG] Tarif akışındayız → recipe_flow_continue mode.")
        return handle_recipe_flow(user_input)

    # Önce heuristik dene (LLM bozulsa bile)
    heuristic = _heuristic_mode_detect(user_input)
    if heuristic in ("shopping", "recipe"):
        print(f"[DEBUG] Heuristic mode: {heuristic}")
        mode = heuristic
        confidence = 1.0
    else:
        # Heuristik karar veremediyse LLM classifier'a bırak
        classification = classify_mode(user_input)
        mode = classification.get("mode", "unknown")
        confidence = classification.get("confidence", 0.0)

        print(f"[DEBUG] LLM classify → Mode: {mode}, Confidence: {confidence}")
        if "error" in classification:
            print(f"[DEBUG] Classifier error: {classification['error']}")

    # Mode'a göre routing
    if mode == "shopping":
        return handle_shopping(user_input)

    if mode == "recipe":
        return handle_recipe(user_input)

    if mode == "recipe_flow_continue":
        return handle_recipe_flow(user_input)

    # Unknown fallback
    return {
        "mode": "unknown",
        "message": "Tam anlayamadım, alışveriş mi yoksa yemek mi yapmak istiyorsun?",
    }
