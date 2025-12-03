from typing import List, Dict, Any
import re
import time

from db.database import Database
from scrapers.migros_scraper import MigrosScraper
from scrapers.getir_scraper import GetirScraper


# Kategori bazında istekler arasında beklenecek süre 
REQUEST_DELAY_BETWEEN_JOBS = 3  # saniye
# Siteler arasında beklenecek süre
REQUEST_DELAY_BETWEEN_SITES = 5  # saniye


#Scape edilecek kategorilerin urlleri
SCRAPE_CONFIG: Dict[str, list[Dict[str, Any]]] = {

    "migros": [
        {
            "url": "https://www.migros.com.tr/meyve-sebze-c-2",
            "top_category": "Meyve - Sebze",
            "max_pages": None
        },
        {
            "url": "https://www.migros.com.tr/et-tavuk-balik-c-3",
            "top_category": "Et - Tavuk - Balık",
            "max_pages": None
        },
        {
            "url": "https://www.migros.com.tr/temel-gida-c-5",
            "top_category": "Temel Gıda",
            "max_pages": None
        },
        {
            "url": "https://www.migros.com.tr/atistirmalik-c-113fb",
            "top_category": "Atıştırmalık",
            "max_pages": None
        },
        {
            "url": "https://www.migros.com.tr/icecek-c-6",
            "top_category": "İçecek",
            "max_pages": None
        },
    ],

    "getir": [
        {
            "url": "https://getir.com/kategori/meyve-sebze-VN2A9ap5Fm/",
            "top_category": "Meyve - Sebze"
        },
        {
            "url": "https://getir.com/kategori/et-tavuk-balik-P1593VdPBd/",
            "top_category": "Et - Tavuk - Balık"
        },
        {
            "url": "https://getir.com/kategori/temel-gida-IQH9bir3bX/",
            "top_category": "Temel Gıda"
        },
        {
            "url": "https://getir.com/kategori/atistirmalik-BaaxwkyV1y/",
            "top_category": "Atıştırmalık"
        },
        {
            "url": "https://getir.com/kategori/su-icecek-ewknEvzsJc/",
            "top_category": "İçecek"
        },
    ],
}


# fiyatlari string olarak çekiyoruz burada tl yi silip floata çevir

def parse_price(raw: Any) -> float | None:
    """
    15.90 TL -> 15.90
    """
    if raw is None:
        return None
    
    s = str(raw).strip()
    if not s:
        return None

    s= s.replace("TL", "").replace("₺", "").strip()

    s = re.sub(r"[^\d,\.]", "", s)
    if not s:
        return None

    # hem nokta hem virgül varsa
    if "," in s and "." in s:
        #noktalari tamamen akdlir, virgülü ondalik yap
        s= s.replace(".", "").replace(",", ".")
    else:
        if "," in s:
            s=s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None

def normalize_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Scraper'lardan gelen ürün listesinde:
    - price ve discounted_price'ı float'a çevirir
    - Diğer alanlara dokunmaz
    """
    normalized: List[Dict[str, Any]] = []

    for p in products:
        item = dict(p)

        item["price"] = parse_price(item.get("price"))
        item["discounted_price"] = parse_price(item.get("discounted_price"))

        normalized.append(item)

    return normalized

def run_migros(db: Database) -> None:
    jobs = SCRAPE_CONFIG.get("migros", [])
    if not jobs:
        return

    scraper = MigrosScraper()
    try:
        for idx, job in enumerate(jobs, start=1):
            url = job["url"]
            top_category = job["top_category"]
            max_pages = job.get("max_pages")

            print(f"[MIGROS] ({idx}/{len(jobs)}) {top_category} -> {url}")

            products = scraper.scrape_main_category(
                main_url=url,
                category_name=top_category,
                max_pages=max_pages,
            )

            products = normalize_products(products)
            db.insert_products(products)
            print(f"[MIGROS] DB'ye yazılan ürün sayısı: {len(products)}")

            # Kategori istekleri arasında bekle
            if idx < len(jobs):
                print(f"[MIGROS] Sonraki kategoriye geçmeden {REQUEST_DELAY_BETWEEN_JOBS}s bekleniyor...")
                time.sleep(REQUEST_DELAY_BETWEEN_JOBS)
    finally:
        scraper.close()



def run_getir(db: Database) -> None:
    jobs = SCRAPE_CONFIG.get("getir", [])
    if not jobs:
        return

    scraper = GetirScraper()
    try:
        for idx, job in enumerate(jobs, start=1):
            url = job["url"]
            top_category = job["top_category"]

            print(f"[GETIR] ({idx}/{len(jobs)}) {top_category} -> {url}")

            products = scraper.scraper_category(
                url=url,
                category_name=top_category,
            )

            products = normalize_products(products)
            db.insert_products(products)
            print(f"[GETIR] DB'ye yazılan ürün sayısı: {len(products)}")

            # Kategori istekleri arasında bekle
            if idx < len(jobs):
                print(f"[GETIR] Sonraki kategoriye geçmeden {REQUEST_DELAY_BETWEEN_JOBS}s bekleniyor...")
                time.sleep(REQUEST_DELAY_BETWEEN_JOBS)
    finally:
        scraper.close()



if __name__ == "__main__":
    db= Database()
    db.init_schema()
    try:
        print("migros scraper running")
        run_migros(db)

        print(f"Siteler arasinda {REQUEST_DELAY_BETWEEN_SITES} kadar bekleniyor")
        time.sleep(REQUEST_DELAY_BETWEEN_SITES)

        print("getir scraper running...")
        run_getir(db)

    finally:
        db.close()
        print("db bağlantisi kesidli")