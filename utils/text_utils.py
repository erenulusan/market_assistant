"""
Ürün isimlerini embed ederken ve search vektör veri tabaninda arama yaparken ayni normalize islemelerini kullanacağiz.
"""

import re

def normalize_text(text: str) -> str:
    if not text:
        return ""

    t= text.lower()
    
    t= (
        t.replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ğ", "g")

    )

    # harf rakam ve bosluk disi karakterleri temizle
    t= re.sub(r"[^a-z0-9]+", " ", t)
    
    #fazla bosluklari temizle
    t= " ".join(t.split())

    return t