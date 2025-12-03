"""
Amaç : 
        - Verilen bir cümle  (yemek tarifi için) önce google translate ile ingilizceye çevrilir.
        - Google translatein outputu dil modeline gönderilir. 
        - Dil modeli yemek tarifi malzemeleri icin json formatinda output üretir.
        - Dil modelinden cikan json formatindaki output tekrar google translate ile tr' ye çevrilir.
        - Evde buluınmasi muhtemel temel mazlemeler (tuz karabiber yağ vs) ayrı bi listeye alinir.
Kullanilacak Teknolojiler: 
                        - deep_translator (GoogleTranslate) : ingilzice - turkce ceviri icin
                        - LLM MODELİ : LLAMA 3.2:3b 

Not: LLAMA 3B paramatreli modeli türkce isimlendirimiş yemekleri cok iyi anlayamadiği icin önce ceviri yapilip sonra tarif malzemeleri alincak.
"""


from deep_translator import GoogleTranslator
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
import json
from rich import print

#kullanilacak dil modeli
llm= ChatOllama(model="llama3.2:3b", temperature=0)

# yemek tarifi malzemeleri icin prompt:
JSON_SYSTEM_PROMPT = """
You are a recipe ingredient extraction assistant.

Task:
- The user will describe a dish they want to cook (in Turkish, but you will see it translated to English).
- Your job is to return a realistic ingredient list for that dish and the number of servings.

STRICTLY RETURN ONLY JSON:
{
  "servings": <number>,
  "recipe": "<dish name>",
  "ingredients": [
    { "name": "<ingredient name>", "quantity": "<quantity with units in a human-readable way>" }
  ]
}

VERY IMPORTANT RULES (READ CAREFULLY):

1. List ONLY the ingredients that the user is likely to NEED TO BUY.
   - Do NOT list basic pantry items unless they are very specific or central.
   - Basic pantry items (that most people already have at home):
     - salt
     - black pepper
     - oil (olive oil, vegetable oil)
     - water
     - sugar
     - flour
     - basic spices (like chili flakes, oregano, cumin) UNLESS the dish is specifically about that spice.

2. If the dish is simple like "pasta", prefer a MINIMAL ingredient list:
   - Example for plain pasta:
     - pasta
     - optionally tomato sauce OR tomato + onion (but keep it simple)
   - Do NOT add fancy ingredients (like parmesan, heavy cream, wine) unless they are clearly necessary or very typical.

3. Use realistic quantities for the given number of servings.
   - If the user does NOT specify servings, assume 2–4 servings (choose a reasonable default like 2 or 4).
   - Quantities should be in friendly units, NOT American-only:
     - Use: grams, ml, "adet", "yemek kaşığı", "çay kaşığı", "su bardağı"
     - Avoid: oz, lb, cup, tbsp, tsp (or convert them to the above styles).
     - For vegetables like onion, garlic, tomato, pepper, etc., prefer quantities in "adet" or "gram", NOT spoon measurements.


4. The recipe name should be short and clear (e.g., "köfte", "makarna", "mercimek çorbası").

5. Do NOT add any explanations, comments, or extra fields.
6. Do NOT wrap the JSON in backticks or ```json.
7. Return ONLY valid JSON exactly in the format described above.
"""


# Evde bulunma ihtimali yüksek temel malzemeler
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
    "sarımsak",
    "soğan tozu",
    "baharat",
]

# Birimleri Türkçe'ye normalize etmek için basit mapping
UNIT_MAP = {
    "oz": "gram",
    "ounce": "gram",
    "lb": "gram",
    "pound": "gram",
    "cup": "su bardağı",
    "cups": "su bardağı",
    "tbsp": "yemek kaşığı",
    "tablespoon": "yemek kaşığı",
    "tablespoons": "yemek kaşığı",
    "tsp": "çay kaşığı",
    "teaspoon": "çay kaşığı",
    "teaspoons": "çay kaşığı",
    "pinch": "bir tutam",
    "clove": "diş",
    "cloves": "diş",
}

def normalize_quantity_text(q: str | None) -> str | None:
    """
    LLM' den gelen quantityde ingizlice birimleri türkçeye maplemek icin
    """
    if not q:
        return q
    
    q_norm= q
    for eng, tr in UNIT_MAP.items():
        q_norm= q_norm.replace(eng, tr)
    return q_norm


def is_pantry_item(name_tr: str) -> bool:
    """
    Malzemenin adindan evde bulunabilecek temel bir sey olup olmadiğini yaklasık olarak tahmiin etmek icin
    """
    n= name_tr.lower()
    for kw in BASIC_PANTRY_KEYWORDS:
        if kw in n:
            return True
    return False


def extract_ingredients(user_text: str) -> dict:
    """
    Verilen türkçe cümleyi:
        - İngilizce cevir
        - LLM ile JSON formatinda tarif malzemelerini al
        - Malzeme isimlerini tekrar türkce cevir
        - Temel malzemeleri ayri listeye koy
    """
    try: 
        english_sentence= GoogleTranslator(source="tr", target="en").translate(user_text)

    except Exception as e:
        print("[bold red]çeviri hatasi[/bold red]", e)
        english_sentence = user_text

    # LLM çağrısı
    messages = [
        SystemMessage(content=JSON_SYSTEM_PROMPT),
        HumanMessage(content=english_sentence),
    ]

    response = llm.invoke(messages).content.strip()

    try:
        data = json.loads(response)
    except Exception as e:
        print("[red]JSON PARSE ERROR[/red]", e)
        print(response)
        return {
            "servings": None,
            "recipe": None,
            "ingredients_to_buy": [],
            "pantry_items": [],
        }

    servings = data.get("servings")
    recipe_en = data.get("recipe")
    ing_raw = data.get("ingredients", [])

    ingredients_to_buy = []
    pantry_items = []

    for ing in ing_raw:
        name_en = ing.get("name")
        quantity_en = ing.get("quantity")

        if not name_en:
            continue

        # TR çeviri
        try:
            name_tr = GoogleTranslator(source="en", target="tr").translate(name_en)
        except:
            name_tr = name_en

        quantity_tr = normalize_quantity_text(quantity_en)

        obj = {
            "name": name_tr,
            "quantity": quantity_tr,
        }

        if is_pantry_item(name_tr):
            pantry_items.append(obj)
        else:
            ingredients_to_buy.append(obj)

    # recipe adı
    try:
        recipe_tr = GoogleTranslator(source="en", target="tr").translate(recipe_en)
    except:
        recipe_tr = recipe_en

    result = {
        "servings": servings,
        "recipe": recipe_tr,
        "ingredients_to_buy": ingredients_to_buy,
        "pantry_items": pantry_items,
    }

    print("\n[cyan]Türkçe JSON:[/cyan]")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n" + "-" * 50)

    return result


if __name__ == "__main__":
    while True:
        txt = input("Yemek (q=quit): ").strip()
        if txt == "q":
            break
        extract_ingredients(txt)