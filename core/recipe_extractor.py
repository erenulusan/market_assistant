"""
Amaç:
    - Kullanıcının Türkçe yazdığı yemek isteğinden,
      alışveriş için gerekli malzemeleri JSON formatında çıkarmak.
    - Evde olması muhtemel temel malzemeleri ayrı listeye ayırmak.

Bu versiyon:
    - LLM: GPT-4o-mini (OpenAI)  -> LangChain üzerinden
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from rich import print

from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


# ENV
ROOT = Path(__file__).resolve().parents[1]  # project root
ENV_PATH = ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# TEMEL MALZEME LİSTESİ (evde olma ihtimali yüksek olanlar)
BASIC_PANTRY_KEYWORDS = [
    "tuz",
    "karabiber",
    "pul biber",
    "toz biber",
    "biberiye",
    "kekik",
    "kimyon",
    "zeytinyağı",
    "ayçiçek yağı",
    "sıvı yağ",
    "şeker",
    "un",
    "su",
    "soğan",
    "sarımsak",
]


# Pydantic modelleri (LLM JSON output’u için)
class Ingredient(BaseModel):
    name: str = Field(..., description="Malzeme adı (Türkçe, kısa ve net)")
    quantity: Optional[str] = Field(
        None,
        description=(
            "Miktar ve birim birlikte, insan okuyabilir formatta. "
            'Örn: "2 adet", "200 gram", "1 su bardağı"'
        ),
    )


class RecipeExtraction(BaseModel):
    servings: Optional[int] = Field(
        None,
        description="Kaç kişilik tarif olduğu (bilmiyorsa 2 veya 4 gibi makul bir sayı seç)",
    )
    recipe: str = Field(..., description="Tarifin kısa ve net adı (Türkçe)")
    ingredients: List[Ingredient] = Field(
        ..., description="Tarif için gereken tüm malzeme listesi"
    )


# LLM + Prompt + Parser
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)

parser = JsonOutputParser(pydantic_object=RecipeExtraction)
FORMAT_INSTRUCTIONS = parser.get_format_instructions()

SYSTEM_PROMPT = """
You are a recipe ingredient extraction assistant.

The user will describe a DISH THEY WANT TO COOK in TURKISH.

Your job:
- Understand the dish.
- Return a realistic ingredient list (in TURKISH) and the number of servings.

STRICTLY RETURN ONLY JSON with this schema:
- servings: integer or null
- recipe: short dish name in Turkish
- ingredients: list of objects with:
    - name: ingredient name in Turkish
    - quantity: quantity + unit in Turkish

VERY IMPORTANT RULES:

1. The output MUST be in TURKISH for both "recipe" and each ingredient "name" + "quantity".

2. Use realistic quantities for the given number of servings.
   - If the user does NOT specify servings, choose 2 or 4.

3. Use FRIENDLY units:
   - gram, ml, adet, yemek kaşığı, çay kaşığı, su bardağı

4. Prefer simple ingredients. Do NOT add unnecessary items.

5. DO NOT add explanations, comments or extra fields.
6. DO NOT wrap the JSON in backticks.

Below are the exact JSON formatting instructions:

{format_instructions}
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "{user_text}"),
    ]
)

chain = prompt | llm | parser


# Yardımcı: temel malzeme mi?
def is_pantry_item(name_tr: str) -> bool:
    """
    Malzeme adından evde bulunabilecek temel bir şey olup olmadığını
    yaklaşık olarak tahmin etmek için (keyword bazlı).
    """
    n = name_tr.lower()
    for kw in BASIC_PANTRY_KEYWORDS:
        if kw in n:
            return True
    return False


# Ana fonksiyon: extract_ingredients
def extract_ingredients(user_text: str) -> Dict[str, Any]:
    """
    Verilen Türkçe cümleyi:
        - LLM ile JSON formatında tarif malzemelerine çevirir
        - Malzemeleri:
            - ingredients_to_buy
            - pantry_items
          olarak ayırır
    """
    try:
        # chain.invoke çıktısı bazı versiyonlarda dict, bazı versiyonlarda Pydantic model olabiliyor
        raw_result = chain.invoke(
            {
                "user_text": user_text,
                "format_instructions": FORMAT_INSTRUCTIONS,
            }
        )

        # Güvenli taraf: dict geldiyse Pydantic modele çevir
        if isinstance(raw_result, dict):
            result = RecipeExtraction.model_validate(raw_result)
        else:
            # Muhtemelen zaten RecipeExtraction instance
            result = raw_result

    except ValidationError as ve:
        print("[bold red]Pydantic ValidationError:[/bold red]", ve)
        return {
            "servings": None,
            "recipe": None,
            "ingredients_to_buy": [],
            "pantry_items": [],
        }
    except Exception as e:
        print("[bold red]LLM / parsing hatası:[/bold red]", e)
        return {
            "servings": None,
            "recipe": None,
            "ingredients_to_buy": [],
            "pantry_items": [],
        }

    # Buradan sonrası Pydantic instance üzerinden
    servings = result.servings
    recipe_name = result.recipe
    ing_raw = result.ingredients

    ingredients_to_buy: List[Dict[str, Any]] = []
    pantry_items: List[Dict[str, Any]] = []

    for ing in ing_raw:
        name = ing.name.strip() if ing.name else ""
        if not name:
            continue

        quantity = ing.quantity.strip() if ing.quantity else None

        obj = {
            "name": name,
            "quantity": quantity,
        }

        if is_pantry_item(name):
            pantry_items.append(obj)
        else:
            ingredients_to_buy.append(obj)

    output = {
        "servings": servings,
        "recipe": recipe_name,
        "ingredients_to_buy": ingredients_to_buy,
        "pantry_items": pantry_items,
    }

    # Terminal için debug output
    print("\n[cyan]Tarif JSON:[/cyan]")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("\n" + "-" * 50)

    return output


# CLI testing
if __name__ == "__main__":
    print(
        "[bold green]Tarif extractor (LangChain + GPT-4o-mini) başlatıldı. Çıkmak için 'q' yaz.[/bold green]\n"
    )

    while True:
        txt = input("Ne pişirmek istiyorsun? (q=quit): ").strip()
        if txt.lower() == "q":
            break
        extract_ingredients(txt)
