// chat.js
const BASE_URL = "http://127.0.0.1:8000";

const chatMessagesEl = document.getElementById("chat-messages");
const chatInputEl = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");

const cartBodyEl = document.getElementById("cart-body");
const cartTotalTextEl = document.getElementById("cart-total-text");
const cartAnalyzeBtnEl = document.getElementById("cart-analyze-btn");

// mode pill
const modeIndicatorEl = document.getElementById("mode-indicator");
const modeIndicatorTagEl = modeIndicatorEl
  ? modeIndicatorEl.querySelector(".tag")
  : null;

// -----------------------------
// Global state
// -----------------------------
let cart = [];
let isSending = false;

// -----------------------------
// Mode indicator helper
// -----------------------------
function setModeIndicator(mode) {
  if (!modeIndicatorEl || !modeIndicatorTagEl) return;

  let label = "–";
  let bg = "rgba(15, 23, 42, 0.9)";
  let border = "rgba(75, 85, 99, 0.9)";
  let color = "#e5e7eb";

  if (mode === "shopping") {
    label = "Alışveriş";
    bg = "rgba(34, 197, 94, 0.12)";
    border = "rgba(34, 197, 94, 0.6)";
    color = "#bbf7d0";
  } else if (mode === "recipe") {
    label = "Tarif";
    bg = "rgba(251, 146, 60, 0.12)";
    border = "rgba(251, 146, 60, 0.6)";
    color = "#fed7aa";
  } else if (mode === "recipe_flow_continue") {
    label = "Tarif akışı";
    bg = "rgba(59, 130, 246, 0.12)";
    border = "rgba(59, 130, 246, 0.6)";
    color = "#bfdbfe";
  } else if (mode === "unknown") {
    label = "Belirsiz";
    bg = "rgba(31, 41, 55, 0.9)";
    border = "rgba(75, 85, 99, 0.9)";
    color = "#e5e7eb";
  }

  modeIndicatorTagEl.textContent = label;
  modeIndicatorEl.style.background = bg;
  modeIndicatorEl.style.borderColor = border;
  modeIndicatorEl.style.color = color;
}

// -----------------------------
// Helper: Chat'e mesaj basma
// -----------------------------
function addMessage(role, text, extraContent = null, opts = {}) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", role === "user" ? "user" : "bot");
  if (opts.loading) {
    msgDiv.classList.add("loading");
  }
  msgDiv.textContent = text;

  if (extraContent) {
    msgDiv.appendChild(extraContent);
  }

  chatMessagesEl.appendChild(msgDiv);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

  return msgDiv;
}

// -----------------------------
// Helper: Sepeti yeniden çiz
// -----------------------------
function renderCart() {
  cartBodyEl.innerHTML = "";

  if (cart.length === 0) {
    const p = document.createElement("p");
    p.classList.add("cart-empty");
    p.textContent = "Sepet boş.";
    cartBodyEl.appendChild(p);
    cartTotalTextEl.textContent = "Toplam: 0.00 TL";
    cartAnalyzeBtnEl.disabled = true;
    return;
  }

  let total = 0;

  cart.forEach((item) => {
    const div = document.createElement("div");
    div.classList.add("cart-item");

    const title = document.createElement("div");
    title.classList.add("cart-item-title");
    title.textContent = `${item.name} (${item.site})`;

    const detail = document.createElement("div");
    detail.textContent = `Fiyat: ${item.price.toFixed(2)} TL  |  Adet: ${
      item.quantity
    }`;

    total += item.price * item.quantity;

    div.appendChild(title);
    div.appendChild(detail);
    cartBodyEl.appendChild(div);
  });

  cartTotalTextEl.textContent = `Toplam: ${total.toFixed(2)} TL`;
  cartAnalyzeBtnEl.disabled = false;
}

// -----------------------------
// Sepete ürün ekle
// -----------------------------
function addToCart(product) {
  const existing = cart.find(
    (c) => c.id === product.id && c.site === product.site
  );

  if (existing) {
    existing.quantity += 1;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      site: product.site,
      price: product.price || 0,
      quantity: 1,
    });
  }

  renderCart();
}

// -----------------------------
// Ürün kartları
// -----------------------------
function buildProductListElement(items) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("product-list");

  (items || []).forEach((item) => {
    const topResults = (item.results || []).slice(0, 3);

    topResults.forEach((res) => {
      const card = document.createElement("div");
      card.classList.add("product-card");

      const title = document.createElement("h4");
      title.textContent = res.name;

      const info1 = document.createElement("p");
      info1.textContent = `Market: ${res.site} | Alt kategori: ${
        res.subcategory || "-"
      }`;

      const effectivePrice = res.price ?? res.discounted_price;
      const priceText =
        effectivePrice != null ? `${effectivePrice.toFixed(2)} TL` : "Fiyat yok";

      const info2 = document.createElement("p");
      info2.textContent = `Fiyat: ${priceText}`;

      const info3 = document.createElement("p");
      info3.textContent = `İstek: ${item.requested_name}`;

      const btn = document.createElement("button");
      btn.textContent = "Sepete ekle";
      btn.addEventListener("click", () => {
        if (effectivePrice == null) {
          alert("Bu ürün için fiyat bulunamadı, sepete eklenemiyor.");
          return;
        }

        addToCart({
          id: res.id,
          name: res.name,
          site: res.site,
          price: effectivePrice,
        });
      });

      card.appendChild(title);
      card.appendChild(info1);
      card.appendChild(info2);
      card.appendChild(info3);
      card.appendChild(btn);

      wrapper.appendChild(card);
    });
  });

  return wrapper;
}

// -----------------------------
// API çağrıları
// -----------------------------

// Agent endpoint – tek giriş noktası
async function callAgent(query) {
  const url = `${BASE_URL}/assistant/agent?q=${encodeURIComponent(query)}`;
  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`HTTP hata kodu: ${res.status}`);
  }
  return res.json();
}

// Tarif ingredient seçimi için, hâlâ direkt alışveriş endpoint'ini kullanıyoruz
async function callShoppingAssistant(query, k = 5) {
  const url = `${BASE_URL}/assistant/shopping-full?q=${encodeURIComponent(
    query
  )}&k=${k}`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP hata kodu: ${res.status}`);
  }
  return res.json();
}

async function analyzeCart() {
  if (cart.length === 0) {
    addMessage("bot", "Sepet şu anda boş görünüyor, önce ürün eklemelisin.");
    return;
  }

  const payload = {
    items: cart.map((item) => ({
      product_id: item.id,
      quantity: item.quantity,
    })),
  };

  const temp = addMessage(
    "bot",
    "Sepetini analiz ediyorum...",
    null,
    { loading: true }
  );

  try {
    const res = await fetch(`${BASE_URL}/basket/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`HTTP hata kodu: ${res.status}`);
    }

    const data = await res.json();
    temp.remove();

    addMessage("bot", data.summary_text || "Sepet analizi sonucu alınamadı.");
  } catch (err) {
    console.error(err);
    temp.remove();
    addMessage(
      "bot",
      "Sepet analizi sırasında bir hata oluştu, lütfen tekrar dene."
    );
  }
}

// -----------------------------
// Tarif flow için ingredient seçimi
// -----------------------------
function buildIngredientSelectElement(ingredients) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("ingredient-select");

  const title = document.createElement("div");
  title.classList.add("ingredient-select-title");
  title.textContent =
    "Eksik malzemeler için market araması yapmamı ister misin? Aşağıdan seç:";
  wrapper.appendChild(title);

  const listDiv = document.createElement("div");
  listDiv.classList.add("ingredient-list");

  (ingredients || []).forEach((ing) => {
    const itemDiv = document.createElement("label");
    itemDiv.classList.add("ingredient-item");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.dataset.name = ing.name || "";

    const span = document.createElement("span");
    const q = ing.quantity ? ` (${ing.quantity})` : "";
    span.textContent = `${ing.name}${q}`;

    itemDiv.appendChild(cb);
    itemDiv.appendChild(span);
    listDiv.appendChild(itemDiv);
  });

  wrapper.appendChild(listDiv);

  const btn = document.createElement("button");
  btn.textContent = "Seçilenler için markette arama yap";

  btn.addEventListener("click", async () => {
    const checkboxes = listDiv.querySelectorAll("input[type='checkbox']");
    const selectedNames = [];
    checkboxes.forEach((cb) => {
      if (cb.checked && cb.dataset.name) {
        selectedNames.push(cb.dataset.name);
      }
    });

    if (selectedNames.length === 0) {
      alert("En az bir malzeme seçmelisin.");
      return;
    }

    const query = selectedNames.join(", ") + " almak istiyorum";
    await runRecipeMarketSearch(query);
  });

  wrapper.appendChild(btn);
  return wrapper;
}

async function runRecipeMarketSearch(query) {
  const temp = addMessage(
    "bot",
    "Seçili malzemeler için market fiyatlarına bakıyorum...",
    null,
    { loading: true }
  );

  try {
    const data = await callShoppingAssistant(query);

    temp.remove();

    const baskets = data.baskets || {};
    const cheapest = baskets.cheapest_single_site;
    const bestMix = baskets.best_mix;

    let summaryLines = [];

    if (cheapest) {
      summaryLines.push(
        `Bu tarif için en ucuz tek market: ${cheapest.site} | Toplam: ${cheapest.total_price.toFixed(
          2
        )} TL`
      );
    }

    if (bestMix) {
      summaryLines.push(
        `Karışık (site karışık) sepet: ${bestMix.total_price.toFixed(2)} TL`
      );
    }

    if (!cheapest && !bestMix) {
      summaryLines.push(
        "Bu malzemeler için sepet önerisi oluşturulamadı (bazı ürünler bulunamamış olabilir)."
      );
    }

    const botText =
      summaryLines.join("\n") +
      "\n\nAşağıda seçtiğin malzemeler için bulduğum ürünleri listeliyorum, istediklerini sepete ekleyebilirsin.";

    const productListEl = buildProductListElement(data.items || []);
    addMessage("bot", botText, productListEl);
  } catch (err) {
    console.error(err);
    temp.remove();
    addMessage("bot", "Market araması sırasında bir hata oluştu.");
  }
}

// -----------------------------
// Agent cevaplarını render et
// -----------------------------
function renderAgentResponse(data) {
  const mode = data.mode || "unknown";
  setModeIndicator(mode);

  // Mode: alışveriş
  if (mode === "shopping") {
    const baskets = data.baskets || {};
    const cheapest = baskets.cheapest_single_site;
    const bestMix = baskets.best_mix;

    let summaryLines = [];

    if (cheapest) {
      summaryLines.push(
        `En ucuz market: ${cheapest.site} | Toplam: ${cheapest.total_price.toFixed(
          2
        )} TL`
      );
    }

    if (bestMix) {
      summaryLines.push(
        `Karışık sepet (birden fazla market): ${bestMix.total_price.toFixed(
          2
        )} TL`
      );
    }

    if (!cheapest && !bestMix) {
      summaryLines.push("Bu ürünler için sepet önerisi oluşturulamadı.");
    }

    const botText =
      "🧺 Bunu alışveriş isteği olarak yorumladım.\n\n" +
      summaryLines.join("\n") +
      "\n\nAşağıda senin için bulduğum ürünleri listeliyorum, beğendiklerini sepete ekleyebilirsin.";

    const productListEl = buildProductListElement(data.items || []);
    addMessage("bot", botText, productListEl);
    return;
  }

  // Mode: tarif çıkarma
  if (mode === "recipe") {
    const recipe = data.recipe || {};
    const ingredientsToBuy = data.ingredients_to_buy || [];
    const pantryItems = data.pantry_items || [];

    const name = recipe.name || "Tarif";
    const servings = recipe.servings ? `${recipe.servings} kişilik` : "";
    const headerLine = servings ? `${name} (${servings})` : name;

    let msg = `🍝 Bunu yemek / tarif isteği olarak yorumladım.\n\n${headerLine}\n\n`;
    msg += "Alman gereken malzemeler:\n";
    if (ingredientsToBuy.length === 0) {
      msg += "- (Eksik malzeme görünmüyor)\n";
    } else {
      ingredientsToBuy.forEach((ing) => {
        const q = ing.quantity ? ` (${ing.quantity})` : "";
        msg += `- ${ing.name}${q}\n`;
      });
    }

    msg += "\nEvde olma ihtimali yüksek olanlar:\n";
    if (pantryItems.length === 0) {
      msg += "- (Temel malzeme yok veya tespit edilemedi)\n";
    } else {
      pantryItems.forEach((ing) => {
        const q = ing.quantity ? ` (${ing.quantity})` : "";
        msg += `- ${ing.name}${q}\n`;
      });
    }

    const extra = buildIngredientSelectElement(ingredientsToBuy);
    addMessage("bot", msg, extra);
    return;
  }

  // Mode: tarif akışı devamı
  if (mode === "recipe_flow_continue") {
    const action = data.action || null;

    if (action === "give_recipe") {
      const steps = data.recipe_steps || "Tarif adımlarını şu an çıkaramadım.";
      addMessage("bot", `🍳 Tarif adımları:\n\n${steps}`);
      return;
    }

    if (action === "market_search") {
      const baskets = data.baskets || {};
      const cheapest = baskets.cheapest_single_site;
      const bestMix = baskets.best_mix;

      let summaryLines = [];

      if (cheapest) {
        summaryLines.push(
          `Bu tarif için en ucuz tek market: ${cheapest.site} | Toplam: ${cheapest.total_price.toFixed(
            2
          )} TL`
        );
      }

      if (bestMix) {
        summaryLines.push(
          `Karışık sepet: ${bestMix.total_price.toFixed(2)} TL`
        );
      }

      if (!cheapest && !bestMix) {
        summaryLines.push(
          "Bu tarif için sepet önerisi oluşturulamadı (bazı ürünler bulunamamış olabilir)."
        );
      }

      const botText =
        summaryLines.join("\n") +
        "\n\nAşağıda bu tarif için bulduğum ürünleri listeliyorum, istediklerini sepete ekleyebilirsin.";

      const productListEl = buildProductListElement(data.items || []);
      addMessage("bot", botText, productListEl);
      return;
    }

    // Aksiyon yoksa düz mesaj
    const msg =
      data.message ||
      "Ne yapmamı istersin? Tarif mi vereyim yoksa market araması mı yapayım?";
    addMessage("bot", msg);
    return;
  }

  // Mode: unknown
  setModeIndicator("unknown");
  const fallbackMsg =
    data.message ||
    "Tam emin olamadım, alışveriş mi yapmak istiyorsun yoksa bir yemek mi pişirmek istiyorsun?";
  addMessage("bot", fallbackMsg);
}

// -----------------------------
// Gönder butonu + Enter
// -----------------------------
async function handleSend() {
  const text = chatInputEl.value.trim();
  if (!text || isSending) return;

  addMessage("user", text);
  chatInputEl.value = "";

  isSending = true;
  chatSendBtn.disabled = true;
  chatInputEl.disabled = true;

  const temp = addMessage("bot", "Düşünüyorum...", null, { loading: true });

  try {
    const data = await callAgent(text);
    temp.remove();
    renderAgentResponse(data);
  } catch (err) {
    console.error(err);
    temp.remove();
    addMessage(
      "bot",
      "Bir hata oluştu, lütfen tekrar dener misin? (backend ayarlarını da kontrol et)"
    );
  } finally {
    isSending = false;
    chatSendBtn.disabled = false;
    chatInputEl.disabled = false;
    chatInputEl.focus();
  }
}

chatSendBtn.addEventListener("click", () => {
  handleSend();
});

chatInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    handleSend();
  }
});

cartAnalyzeBtnEl.addEventListener("click", () => {
  analyzeCart();
});

// İlk sepet render + başlangıç mesajı
renderCart();
setModeIndicator("unknown");
addMessage(
  "bot",
  "Merhaba, ben Market Assistan.\n\nTek cümleyle hem market alışverişini hem de yapmak istediğin yemeği anlatabilirsin"
);
