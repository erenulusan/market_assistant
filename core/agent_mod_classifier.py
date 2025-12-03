from __future__ import annotations
from typing import Literal, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# JSON OUTPUT MODEL
class ModeResult(BaseModel):
    mode: Literal["shopping", "recipe", "recipe_flow_continue", "unknown"] = Field(
        ...,
        description=(
            "shopping = alışveriş/ürün alma isteği,"
            "recipe = yemek/tarif çıkarma isteği,"
            "recipe_flow_continue = tarif sonrası kullanıcı yönlendirmesi,"
            "unknown = kesin değil, kullanıcıya soru sorulmalı."
        )
    )
    confidence: float = Field(
        ...,
        description="0-1 arası güven skoru"
    )


parser = JsonOutputParser(pydantic_object=ModeResult)
FORMAT_INSTRUCTIONS = parser.get_format_instructions()


# LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)


# PROMPT

SYSTEM_PROMPT = """
You are a classification assistant. The user will send Turkish sentences.

Your job is to decide which MODE this input belongs to.

MODES:
- "shopping": User wants to buy items. 
   Examples: "2 litre süt alacağım", "alışveriş yapacağım", "market listesi çıkar", 
   "patates, kola, makarna alayım", "şunları sepete ekle".

- "recipe": User wants a RECIPE or recipe-ingredient extraction.
   Examples: "domates soslu makarna yapmak istiyorum",
             "köfte yapmak istiyorum",
             "tarif çıkart", 
             "bunun için hangi malzemeler gerekli?"

- "recipe_flow_continue": The user is in the RECIPE FLOW and makes a decision about NEXT ACTION.
   Examples:
   - "tarif ver"
   - "market araması yap"
   - "malzemeler için en ucuz marketi bul"
   - "tamam devam et"
   - "evet, ürünleri ara"
   - "bu yemek için tarif ver"
   - "bana bunun tarifini çıkar"

- "unknown": Ambiguous, cannot decide clearly. In this case the agent should ask the user a question.

IMPORTANT NOTES:
- Return ONLY JSON. No explanation.
- Confidence must be 0.0–1.0.
- THINK CAREFULLY.

FORMAT (VERY IMPORTANT):
{format_instructions}
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "{user_input}")
    ]
)

chain = prompt | llm | parser


# MAIN FUNCTION

def classify_mode(user_input: str) -> Dict[str, Any]:
    """
    Returns: { mode: str, confidence: float }

    mode: "shopping" | "recipe" | "recipe_flow_continue" | "unknown"
    """
    try:
        result: ModeResult = chain.invoke(
            {
                "user_input": user_input,
                "format_instructions": FORMAT_INSTRUCTIONS,
            }
        )
        return result.dict()
    except Exception as e:
        # Fail-safe: her durumda dict dön
        return {
            "mode": "unknown",
            "confidence": 0.0,
            "error": str(e),
        }
