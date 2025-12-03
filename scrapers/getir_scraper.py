from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException


class GetirScraper:
    def __init__(self, driver= None, wait_time=10):
        self.driver= webdriver.Chrome()
        self.wait_time= wait_time

    def scraper_category(self, url, category_name=None):
        self.driver.get(url)

        WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "article"))
        )
        
        product_cards= self.driver.find_elements(By.TAG_NAME, "article")
        products= []

        for card in product_cards:
            raw_name= self._get_name(card)
            paragraph= self._get_paragraph(card)
            # None ise bos string
            name_part= raw_name or ""
            paragraph_part= paragraph or ""

            name= (name_part + " " + paragraph_part).strip()
            if not name: continue

            price, discounted_price= self._get_prices(card)
            subcategory = self._get_subcategory(card)

            # ilk classlar dışarıda kaldığı için bunlar manuel  doldurulacak 
            if not subcategory:
                subcategory= "Manuel"

            products.append({
                "site": "getir",
                "top_category": category_name,
                "subcategory": subcategory,
                "name": name,
                "price": price,
                "discounted_price": discounted_price,
            })  

        return products


    # yardimci fonksiyonlar
    # kategorileri de sub categoriye ayirmak için bir fonksiyon daha ekleyelim mesela (su icecek kategorisinde kolayı -> gazli icecek kategorisine atmak için)
    def _get_subcategory(self, card):
        """
        ürünleri alt kategorilere ayirmak için kartlarin üstündeki titlelari çeken fonksiyon 
        - Her ürün karti için : en yakin anchor  ve içindeki h5 etiketini çek 
        """
        try:
            wrapper = card.find_element(By.XPATH,"./ancestor::div[@data-testid='card'][1]")
            title_el = wrapper.find_element(By.CSS_SELECTOR,"h5[data-testid='title']")
            return title_el.text.strip()

        except NoSuchElementException:
            return None


    def _get_name(self, card):
        """
        ürün adını paragraph divinin üstündeki spandan al
        """
        try: 
            paragraph_el = card.find_element(By.CSS_SELECTOR,"div[data-testid='paragraph']")
            name_el = paragraph_el.find_element(By.XPATH,"./preceding-sibling::span[@data-testid='text'][1]")

            return name_el.text.strip()

        except NoSuchElementException:
            return None


    def _get_prices(self, card):
        """
        Getir ürün kartlarından fiyatları çeker.
        - İndirim yoksa: original_price = None, discounted_price = güncel fiyat
        - İndirim varsa: original_price = eski fiyat, discounted_price = güncel fiyat
        """
        original_price = None
        discounted_price = None

        try:
            # Fiyatların olduğu container
            price_container = card.find_element(By.CSS_SELECTOR,"div.sc-c016d6c1-5" )

            # İçindeki tüm spanlar
            price_spans = price_container.find_elements(By.CSS_SELECTOR,"span[data-testid='text']")

            # TL geçenleri filtrlere
            prices = [p.text.strip() for p in price_spans if "TL" in p.text]

            if len(prices) == 1:
                # indirimsiz ürün
                discounted_price = prices[0]

            elif len(prices) >= 2:
                # İlk fiyat: eski (yüksek olan)
                # Son fiyat: güncel (indirimli olan)
                original_price = prices[0]
                discounted_price = prices[-1]

        except NoSuchElementException:
            pass

        return original_price, discounted_price

    def _get_paragraph(self, card):
        """
        ürün açıklamasını çeken fonksiyon
        """
        try:
            return card.find_element(By.CSS_SELECTOR, "div[data-testid='paragraph']").text

        except NoSuchElementException:
            return None

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    url = "https://getir.com/kategori/su-icecek-ewknEvzsJc/"

    scraper = GetirScraper()
    data = scraper.scraper_category(url, category_name="Su & İçecek")

    for p in data[:50]:
        print(
            f"[GETIR] {p['top_category']} / {p['subcategory']} -> "
            f"{p['name']} | price: {p['price']} | disc: {p['discounted_price']}"
        )

    scraper.close()