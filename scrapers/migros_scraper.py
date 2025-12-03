from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from rich import print
from urllib.parse import urljoin
"""
diğer sitelerden farkli olarak burada ürünler sayfa sayfa load ediliyor.
Yani sayfa geçişi butonu inaktif olana kadar devam edeceğiz. 
"""
"""
sub category eklemek icin subcategory isimlerini alip a etiketlerindeki hreflere yönlendirme yaparak subcategory isaretlemesi yapilacak
"""

class MigrosScraper:
    BASE_URL = "https://www.migros.com.tr"
    
    def __init__(self, driver=None, wait_time=10):
        self.driver = driver or webdriver.Chrome()
        self.wait_time = wait_time


    def scrape_main_category(self, main_url, category_name=None, max_pages=None):
        self.driver.get(main_url)

        # Alt kategori elementlerini bul
        WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.filter__subcategories div.items")
            )
        )
        subcat_elems = self.driver.find_elements(
            By.CSS_SELECTOR, "div.filter__subcategories div.items a"
        )

        #  WebElement'leri hemen STRING'e çevir (stale olmadan önce)
        subcats = []
        for el in subcat_elems:
            href_raw = el.get_attribute("href") or el.get_attribute("data-href") or ""
            href = urljoin(self.BASE_URL, href_raw)

            raw_text = el.text.strip()              # "Gazlı İçecek (167)"
            subcat_name = raw_text.split("(")[0].strip()  # "Gazlı İçecek"

            subcats.append((subcat_name, href))

        all_products = []

        for subcat_name, href in subcats:
            print(f"[bold cyan]Subkategori: {subcat_name} -> {href}[/bold cyan]")

            products = self._scrape_pages(
                href,
                category_name=category_name,
                subcategory_name=subcat_name,
                max_pages=max_pages
            )
            all_products.extend(products)

        return all_products

    def _scrape_pages(self, url, category_name=None, subcategory_name= None, max_pages=None):
        self.driver.get(url)
        all_products= []
        current_page= 1

        while True:

            try:
                WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "sm-list-page-item"))
                )
            except TimeoutException:
                print(f"[bold red]Timeout: Ürün kartları yüklenmedi bu alt kategoriyi atla -> {url}[/bold red]")
                break  # bu subcategory için döngüyü bitir

            product_cards = self.driver.find_elements(By.CSS_SELECTOR, "sm-list-page-item")
            print(f"[bold red] Sayfa {current_page} - kart sayısı: {len(product_cards)} [/bold red]" )

            if not product_cards:
                print("[bold red]Hiç ürün kartı bulunamadı bu alt kategoriyi atla[/bold red]")
                break

            for card in product_cards:
                name = self._get_name(card)
                price, discounted_price = self._get_prices(card)

                all_products.append({
                    "site": "migros",
                    "top_category": category_name,
                    "subcategory": subcategory_name,
                    "name": name,
                    "price": price,
                    "discounted_price": discounted_price
                })

            print(f"bu sayfada eklenen ürün sayisi : {len(product_cards)}")


            if max_pages is not None and current_page >= max_pages:
                break

            #sonraki sayfa butonunu bul
            try: 
                next_btn= self.driver.find_element(By.ID, "pagination-button-next" )
            except NoSuchElementException:
                break

            #inaktif mi kontrol et
            disabled_attr= next_btn.get_attribute("disabled")
            if disabled_attr is not None:
                print("Son Sayfa")
                break

            # sonraki sayfaya tikla 
            self.driver.execute_script("arguments[0].click();", next_btn)
            current_page += 1

            # sayfa değişince ürünlerin yüklenmesini bekle
            WebDriverWait(self.driver, self.wait_time).until(EC.staleness_of(product_cards[0]))
            
        return all_products

    # yardimci fonksiyonlar
    
    #isim
    def _get_name(self, card):
        try:
            name_el = card.find_element(By.CSS_SELECTOR, "a#product-name")
            return name_el.text.strip()
        except:
            return None

    #fiyat
    def _get_prices(self, card):
        """
        - Money ile: Diğer sitelere göre farklı aslında indirimli fiyat değil money ile ibaresi
                    - En az 2 tane TL'li fiyat var , original_price= 1.fiyat , discounted_price= son fiyat
        - İyi fiyat etiketi : - container içinde "iyi fiyat" ibaresi geçer
                              - bir fiyat vardir
                              - discounted_price = iyi fiyat, original_price= None
        - Normal : tek fiyat vardır (original_price= fiyat, discounted_price= None)
        """
        original_price= None
        discounted_price= None

        try: 
            price_container= card.find_element(By.CSS_SELECTOR, 'div.price-container')
        except NoSuchElementException:
            return original_price, discounted_price

        container_text= price_container.text.lower()
        
        single_price_spans= price_container.find_elements(By.CSS_SELECTOR, "span.single-price-amount")
        sale_price_divs= price_container.find_elements(By.CSS_SELECTOR, "div#sale-price")
        no_discount_spans= price_container.find_elements(By.CSS_SELECTOR, "fe-product-price#price-no-discount span")

        #money ile
        if "money ile" in container_text and single_price_spans and sale_price_divs:
            original_price= single_price_spans[0].text.strip()
            discounted_price= sale_price_divs[0].text.strip()

        elif "iyi fiyat" in container_text and sale_price_divs:
            original_price= None
            discounted_price= sale_price_divs[0].text.strip()

        elif no_discount_spans:
            original_price= no_discount_spans[0].text.strip()

        return original_price, discounted_price

    def close(self):
        self.driver.quit()




if __name__== "__main__":
    scraper= MigrosScraper()
    main_url= "https://www.migros.com.tr/icecek-c-6?sayfa=1"
    data= scraper.scrape_main_category(main_url, category_name="İcecek", max_pages=None)

    for p in  data[:250]:
        print(p)

    scraper.close()