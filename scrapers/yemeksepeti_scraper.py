from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from rich import print

class YsScraper:
    def __init__(self, driver=None, wait_time=10):
        self.driver= webdriver.Chrome()
        self.wait_time= wait_time
    

    def scraper_category(self, url, category_name):
        self.driver.get(url)
        
        #adres secin penceresini kapat
        self._close_address_modal()

        WebDriverWait(self.driver, self.wait_time).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.product-grid li"))
        )

        product_cards= self.driver.find_elements(By.CSS_SELECTOR, "ul.product-grid >li")
        products= []

        for card in product_cards:
            name= self._get_name(card)
            price, discounted_price= self._get_prices(card)
            subcategory= self._get_subcategory(card)

            products.append({
                "site": "yemeksepeti",       
                "top_category": category_name, 
                "subcategory": subcategory,
                "name": name,
                "price": price,
                "discounted_price": discounted_price,
            })
        return products

    #yardımcı fonksiyonlar


    def _close_address_modal(self):
        """
        adres pop- upını kapatmak için yardimci fonksiyon
        önce siteye gireceğiz bu acılan pencereyi kapatip sonra diğer fonksiyonlari çağiracağiz
        """
        close_btn = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-testid='no-address-modal-close-button']")
            )
        )
        close_btn.click()


    def _get_name(self, card):
        name= card.find_element(By.CSS_SELECTOR, "p.groceries-product-card-name")
        return name.text.strip()

    def _get_subcategory(self, card):
        """
        en yakın ancestor: div.swimlane-as-grid
        -h2[itemopromp-='name'] den altkategori adini almak için
        """
        try: 
            wrapper= card.find_element(By.XPATH, "./ancestor::div[contains(@class,'swimlane-as-grid')][1]")
            name_el = wrapper.find_element(By.CSS_SELECTOR, "h2[itemprop='name']")
            return name_el.text.strip()

        except NoSuchElementException:
            return None
            

    def _get_prices(self, card):
        """
        Yemeksepeti Market ürün kartlarından fiyatları çeker.
        - İndirim yoksa: original_price = None, discounted_price = güncel fiyat
        - İndirim varsa: original_price = eski fiyat, discounted_price = güncel fiyat
        """
        original_price = None
        discounted_price = None  # her zaman güncel fiyat

        try:
            price_container = card.find_element(
                By.CSS_SELECTOR,
                "div[data-testid='groceries-product-card__prices']"
            )
        
            # span.groceries-product-card-price içinde
            discount_els = price_container.find_elements(
                By.CSS_SELECTOR,
                "span.groceries-product-card-price"
            )
            if discount_els:
                discounted_price = discount_els[0].text.strip()

            original_els = price_container.find_elements(
                By.CSS_SELECTOR,
                "span.groceries-product-card-price-before-discount"
            )
            if original_els:
                original_price = original_els[0].text.strip()

        except NoSuchElementException:
            # Fiyat bulunamazsa (tükendi vs.) None kalsın
            pass

        return original_price, discounted_price

    def close(self):
        self.driver.quit()




if __name__ == "__main__":
    url= "https://www.yemeksepeti.com/darkstore/xghk/yemeksepeti-market-celiktepe-istanbul/category/829c4f2e-fbf7-468c-bd6e-2c84a65cf092"

    scraper= YsScraper()
    data = scraper.scraper_category(url, category_name="Atistirmalik")

    for p in data[:200]:
        print(f"ürün adi :{p['name']} - ürün normal fiyat {p['price']} - indirimli fiyat (varsa) : {p['discounted_price']} - subcategory {p['subcategory']}")

    scraper.close()