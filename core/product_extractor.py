"""
Amaç: kullanicinin dogal dilde yazdiği alisveris cümlesinden ürünleri json formatinda extract etmek.
Örnek:
    - 2 litre kola 1 paket pastavilla kuskus makarna, ve 6 adet yumurta almak istiyorum.

json çiktisi:
{
  "items": [
    {"name": "kola", "quantity": 2, "unit": "litre", "subcategory": "Gazlı İçecek"},
    {"name": "pastavilla kuskus makarna", "quantity": 1, "unit": "paket", "subcategory": "Makarna"},
    {"name": "yumurta", "quantity": 6, "unit": "adet", "subcategory": null}
  ]
}

- subcategory sütununu önceden normalize edip mapping islemi yapmistik.
- Burada da json çiktisinda subcategory isimlerini verip ayrica subcategory olarak da extract etmeye çalışiyoruz.
- Eğer subcategory bulabilirse json çiktisina ekleyecek, emin olamazsa None döndürecek.
- Bu sayede search kisminda ürün ararken subcategory ile filtre yapabileceğiz.
"""

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
import json
from rich import print


SUBCATEGORIES = [
    "Makarna",
    "Sos",
    "Salça",
    "Kraker",
    "Çikolata",
    "Bar",
    "Sakız & Şekerleme",
    "Tatlı",
    "Su",
    "Gazlı İçecek",
    "Gazsız İçecek",
    "Maden Suyu",
    "Meyve Suyu",
    "Enerji İçeceği",
    "Fonksiyonel İçecekler",
    "Zeytinyağı",
    "Sıvı Yağ",
    "Kırmızı Et",
    "Beyaz Et",
    "Balık ve Deniz Ürünleri",
]


# Kullanilacak LLM (lokalde Ollama )
llm = ChatOllama(model="llama3.2:3b", temperature=0)

# System promptu
JSON_SYSTEM_PROMPT = f"""
You are a shopping list extraction assistant.

Your task:
- Read the user's sentence.
- Find every product the user wants to buy.
- For each product extract:
  - "name": short product name in Turkish
  - "quantity": numeric value or null
  - "unit": string or null
  - "subcategory": EXACTLY one of the allowed categories listed below, or null if unsure.

Allowed subcategories (Turkish) and meanings:
- Makarna : kuru makarna ürünleri (ör: kelebek makarna, kuskus)
- Sos : mayonez, ketçap, hardal, pesto
- Salça : domates salçası, biber salçası
- Kraker : kraker, çubuk kraker
- Çikolata : tablet çikolata, sütlü / bitter
- Bar : çikolata bar, gofret bar
- Sakız & Şekerleme : sakız, jelibon, draje
- Tatlı : puding, kek karışımı
- Su : içme suyu
- Gazlı İçecek : kola, gazoz, fanta
- Gazsız İçecek : ice tea, limonata, meyveli soğuk içecekler
- Maden Suyu : sade veya aromalı maden suyu
- Meyve Suyu : %100 meyve suyu, nektar
- Enerji İçeceği : red bull, burn vb.
- Fonksiyonel İçecekler : kombucha, vitaminli sular
- Zeytinyağı : sızma / riviera zeytinyağı
- Sıvı Yağ : ayçiçek yağı, mısır yağı
- Kırmızı Et : kıyma, kuşbaşı, biftek
- Beyaz Et : tavuk, hindi
- Balık ve Deniz Ürünleri : taze balık, karides, ton balığı

Important rules:
1. A SINGLE product can have brand + type + category in its name (for example "pastavilla kuskus makarna").
   In that case, you MUST treat it as ONE item, NOT multiple items.
   - DO NOT split "pastavilla", "kuskus", "makarna" into separate items.
   - Correct: one item with name "pastavilla kuskus makarna".
2. Similarly, "coca cola 2.5 lt" is ONE product, not "coca" + "cola".
3. If you are unsure about subcategory, use null.
4. Do NOT invent new categories.
5. Use ONLY these subcategory strings exactly (case-insensitive is ok, but spelling must match).

STRICT JSON OUTPUT FORMAT:
{{
  "items": [
    {{
      "name": "product name",
      "quantity": 2,
      "unit": "adet",
      "subcategory": "category or null"
    }}
  ]
}}

Do NOT add explanations.
Do NOT add comments.
Do NOT wrap the JSON in backticks.

FEW-SHOT EXAMPLES:

User: "2 tane ekmek ve 1 litre fanta"
Output:
{{
  "items": [
    {{ "name": "ekmek", "quantity": 2, "unit": "adet", "subcategory": null }},
    {{ "name": "fanta", "quantity": 1, "unit": "litre", "subcategory": "Gazlı İçecek" }}
  ]
}}

User: "bir paket makarna lütfen"
Output:
{{
  "items": [
    {{ "name": "makarna", "quantity": 1, "unit": "paket", "subcategory": "Makarna" }}
  ]
}}

User: "domates salçası"
Output:
{{
  "items": [
    {{ "name": "domates salçası", "quantity": null, "unit": null, "subcategory": "Salça" }}
  ]
}}

User: "pastavilla kuskus makarna ve coca cola 2.5 lt"
Output:
{{
  "items": [
    {{
      "name": "pastavilla kuskus makarna",
      "quantity": 1,
      "unit": "paket",
      "subcategory": "Makarna"
    }},
    {{
      "name": "coca cola",
      "quantity": 2.5,
      "unit": "litre",
      "subcategory": "Gazlı İçecek"
    }}
  ]
}}
"""



def _normalize_subcategory(s: str | None) -> str | None:
    """
    LLM'den gelen subcategory string'ini SUBCATEGORIES içinden
    canonical hale getirir. Yoksa None döndür.
    """
    if not s:
        return None
    s = s.strip().lower()
    for cat in SUBCATEGORIES:
        if s == cat.strip().lower():
            return cat
    return None


def extract_shopping_items(user_text: str) -> dict:
    """
    Verilen cümleden ürün listesini çıkar.
    Hata olursa {"items": []} döndür.
    """
    messages = [
        SystemMessage(content=JSON_SYSTEM_PROMPT),
        HumanMessage(content=user_text),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        print("[bold red]JSON PARSING HATASI:[/bold red]", e)
        print(raw)
        return {"items": []}

    items = []
    for item in data.get("items", []):
        name = (item.get("name") or "").strip()
        if not name:
            continue

        # quantity -> numeric veya None
        q = item.get("quantity")
        if isinstance(q, str):
            try:
                q = float(q.replace(",", "."))
            except Exception:
                q = None

        unit = item.get("unit")
        if isinstance(unit, str):
            unit = unit.strip() or None

        subcat_raw = item.get("subcategory")
        subcat = _normalize_subcategory(subcat_raw) if subcat_raw else None

        items.append(
            {
                "name": name,
                "quantity": q,
                "unit": unit,
                "subcategory": subcat,
            }
        )

    return {"items": items}


if __name__ == "__main__":
    print("[bold green]Alışveriş extract aracı başlatıldı. Çıkmak için 'q' bas.[/bold green]\n")

    while True:
        text = input("Sorgu: ").strip()
        if text.lower() == "q":
            print("bitti")
            break

        result = extract_shopping_items(text)
        print("\n[bold cyan]JSON çıktısı:[/bold cyan]")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-------")
