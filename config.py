import os 
from pathlib import Path

# path ayarlari
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR= ROOT_DIR / "data"
DB_PATH= DATA_DIR / "market.db"

# embedding ve faiss yollari
EMB_PATH= DATA_DIR / "product_embeddings.npy"
ID_PATH = DATA_DIR / "product_ids.npy"
INDEX_PATH= DATA_DIR / "product_index.faiss"


#model 
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LLM_MODEL_NAME = "llama3.2:3b"


#arama ağirliklari
SEARCH_WEIGHTS= {
    "SEMANTIC_TOP_K": 50,
    "LEXICAL_WEIGHT": 0.3,
    "TAG_WEIGHT": 0.5,
    "KEYWORD_BONUS": 0.4
}

# Scraper ayarlari

SCRAPE_DELAY_JOBS = 3
SCRAPE_DELAY_SITES = 5

SCRAPE_URLS = {
    "migros": [
        {"url": "https://www.migros.com.tr/meyve-sebze-c-2", "top_category": "Meyve - Sebze"},
        {"url": "https://www.migros.com.tr/et-tavuk-balik-c-3", "top_category": "Et - Tavuk - Balık"},
        {"url": "https://www.migros.com.tr/temel-gida-c-5", "top_category": "Temel Gıda"},
        {"url": "https://www.migros.com.tr/atistirmalik-c-113fb", "top_category": "Atıştırmalık"},
        {"url": "https://www.migros.com.tr/icecek-c-6", "top_category": "İçecek"},
    ],
    "getir": [
        {"url": "https://getir.com/kategori/meyve-sebze-VN2A9ap5Fm/", "top_category": "Meyve - Sebze"},
        {"url": "https://getir.com/kategori/et-tavuk-balik-P1593VdPBd/", "top_category": "Et - Tavuk - Balık"},
        {"url": "https://getir.com/kategori/temel-gida-IQH9bir3bX/", "top_category": "Temel Gıda"},
        {"url": "https://getir.com/kategori/atistirmalik-BaaxwkyV1y/", "top_category": "Atıştırmalık"},
        {"url": "https://getir.com/kategori/su-icecek-ewknEvzsJc/", "top_category": "İçecek"},
    ]
}