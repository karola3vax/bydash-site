const PRODUCT_PRICE_USD = 34.99;
const FALLBACK_USD_TRY_RATE = 45;
const PRICE_REFRESH_INTERVAL_MS = 4000;
const DISPLAY_RATE_DRIFT_LIMIT = 0.18;
const API_BASE = window.DASH_API_BASE || "";
const API_BASES = Array.from(new Set([API_BASE, "", "http://127.0.0.1:4193"].filter((value) => value !== null)));
const SESSION_STORAGE_KEY = "dash-session-id";

const localizedImages = {
  2: "assets/localized/winnie-02-saglikli-kacamak.jpeg",
  3: "assets/localized/winnie-03-disney-sihrini.jpeg",
  4: "assets/localized/winnie-04-kolay-yol.jpeg",
  5: "assets/localized/winnie-05-yer-kaplamayan.jpeg",
  6: "assets/localized/winnie-06-olc-erit.jpeg",
  7: "assets/localized/winnie-07-hediye.jpeg",
  8: "assets/localized/winnie-08-disney-dash.jpeg"
};

const variants = [
  {
    key: "winnie",
    id: "44802965635126",
    name: "Winnie The Pooh",
    sku: "DAPP15009",
    start: 1,
    end: 8
  },
  {
    key: "toy-story",
    id: "44936477081654",
    name: "Toy Story",
    sku: "DAPP15008",
    start: 27,
    end: 36
  },
  {
    key: "moana",
    id: "45066779197494",
    name: "Moana",
    sku: "DAPP15007",
    start: 37,
    end: 39
  },
  {
    key: "mickey-minnie",
    id: "44094983012406",
    name: "Mickey & Minnie",
    sku: "DDYAP150CM4",
    start: 9,
    end: 14
  },
  {
    key: "princess",
    id: "44161061027894",
    name: "Princess",
    sku: "DDYAP1503PK4",
    start: 15,
    end: 20
  },
  {
    key: "stitch",
    id: "44094983077942",
    name: "Stitch",
    sku: "DDYAP1502BU4",
    start: 21,
    end: 26
  }
];

const styleOptions = [
  { label: "Açık Turkuaz", image: "assets/styles/aqua.jpg", external: true, available: true },
  { label: "Beyaz", image: "assets/styles/white.jpg", external: true, available: true },
  { label: "Kırmızı", image: "assets/styles/red.jpg", external: true, available: true },
  { label: "Açık Mavi", image: "assets/styles/dream-blue.jpg", external: true, available: false },
  { label: "Krem", image: "assets/styles/cream.jpg", external: true, available: false },
  { label: "Lavanta", image: "assets/styles/lavender.jpg", external: true, available: false },
  { label: "Peanuts\u00ae Sarı", image: "assets/styles/peanuts-yellow.jpg", external: true, available: true },
  { label: "Prenses", image: "assets/products/product-15.jpg", variantKey: "princess", available: true },
  { label: "Mickey & Minnie", image: "assets/products/product-09.jpg", variantKey: "mickey-minnie", available: true },
  { label: "Stitch", image: "assets/products/product-21.jpg", variantKey: "stitch", available: true },
  { label: "Winnie The Pooh", image: "assets/products/product-01.jpg", variantKey: "winnie", available: true },
  { label: "Toy Story", image: "assets/products/product-27.jpg", variantKey: "toy-story", available: true },
  { label: "Moana", image: "assets/products/product-37.jpg", variantKey: "moana", available: true }
];

const searchItems = [
  "Mısır Patlatma Makineleri",
  "Çok Amaçlı Makineler",
  "Dondurma Makineleri",
  "Disney | Dash",
  "Peanuts x Dash",
  "Waffle Makineleri",
  "Air Fryer",
  "Fresh Pop Mısır Patlatma Makinesi"
];

const allImages = Array.from({ length: 39 }, (_, index) => {
  const number = index + 1;
  const variant = variants.find((item) => number >= item.start && number <= item.end) || variants[0];
  return {
    index,
    number,
    src: localizedImages[number] || `assets/products/product-${String(number).padStart(2, "0")}.jpg`,
    alt: `Fresh Pop Mısır Patlatma Makinesi Disney | Dash ${variant.name}`,
    variantKey: variant.key
  };
});

const state = {
  selectedVariant: variants[0],
  selectedImageIndex: 0,
  quantity: 1,
  sessionId: getSessionId(),
  backendReady: false,
  pricing: fallbackPricing(),
  displayPricing: fallbackPricing(),
  pricingHasSynced: false,
  pricingRequestInFlight: false,
  priceTickDirection: 1,
  cart: loadCart(),
  featureIndex: 0
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  renderThumbnails();
  renderStyleOptions();
  renderMedia();
  renderPricing();
  renderCart();
  renderSearchResults(searchItems);
  bindEvents();
  syncFromQuery();
  hydratePricing();
  startPricingRefresh();
  hydrateBackendCart();
});

function cacheDom() {
  dom.body = document.body;
  dom.overlay = document.querySelector("[data-overlay]");
  dom.mainMedia = document.querySelector("#main-media");
  dom.thumbnails = document.querySelector("[data-thumbnails]");
  dom.styleOptions = document.querySelector("[data-style-options]");
  dom.mediaCurrent = document.querySelector("[data-media-current]");
  dom.mediaTotal = document.querySelector("[data-media-total]");
  dom.modalCurrent = document.querySelector("[data-modal-current]");
  dom.modalTotal = document.querySelector("[data-modal-total]");
  dom.modalImage = document.querySelector("[data-modal-image]");
  dom.mediaModal = document.querySelector("[data-media-modal]");
  dom.quantity = document.querySelector("[data-quantity]");
  dom.sku = document.querySelector("[data-sku]");
  dom.cartDrawer = document.querySelector("[data-cart-drawer]");
  dom.menuDrawer = document.querySelector("[data-menu-drawer]");
  dom.searchModal = document.querySelector("[data-search-modal]");
  dom.cartCount = document.querySelector("[data-cart-count]");
  dom.cartEmpty = document.querySelector("[data-cart-empty]");
  dom.cartFilled = document.querySelector("[data-cart-filled]");
  dom.cartItems = document.querySelector("[data-cart-items]");
  dom.cartTotal = document.querySelector("[data-cart-total]");
  dom.toast = document.querySelector("[data-toast]");
  dom.featureTrack = document.querySelector("[data-feature-track]");
  dom.featureCurrent = document.querySelector("[data-feature-current]");
  dom.searchResults = document.querySelector("[data-search-results]");
  dom.reviewModal = document.querySelector("[data-review-modal]");
  dom.reviewForm = document.querySelector("[data-review-form]");
  dom.reviewList = document.querySelector("[data-review-list]");
  dom.profileModal = document.querySelector("[data-profile-modal]");
  dom.profileModalImage = document.querySelector("[data-profile-modal-image]");
  dom.profileModalName = document.querySelector("[data-profile-modal-name]");
  dom.productPrice = document.querySelector("[data-product-price]");
  dom.productPriceTry = document.querySelector("[data-product-price-try]");
  dom.productPriceUsd = document.querySelector("[data-product-price-usd]");
  dom.salePrice = document.querySelector("[data-sale-price]");
  dom.fxRate = document.querySelector("[data-fx-rate]");
  dom.installmentThreshold = document.querySelector("[data-installment-threshold]");
  dom.freeShippingThresholds = document.querySelectorAll("[data-free-shipping-threshold]");
  dom.relatedPrices = document.querySelectorAll("[data-related-price]");
}

function bindEvents() {
  document.querySelector("[data-product-form]").addEventListener("submit", (event) => {
    event.preventDefault();
    addToCart();
  });

  document.querySelector("[data-quantity-minus]").addEventListener("click", () => setQuantity(state.quantity - 1));
  document.querySelector("[data-quantity-plus]").addEventListener("click", () => setQuantity(state.quantity + 1));
  dom.quantity.addEventListener("change", () => setQuantity(Number(dom.quantity.value)));

  document.querySelector("[data-open-media]").addEventListener("click", openMediaModal);
  document.querySelector("[data-close-media]").addEventListener("click", closeMediaModal);
  document.querySelector("[data-media-prev]").addEventListener("click", () => moveMedia(-1));
  document.querySelector("[data-media-next]").addEventListener("click", () => moveMedia(1));
  document.querySelector("[data-mobile-media-prev]").addEventListener("click", () => moveMedia(-1));
  document.querySelector("[data-mobile-media-next]").addEventListener("click", () => moveMedia(1));

  document.querySelector("[data-open-cart]").addEventListener("click", () => openDrawer(dom.cartDrawer));
  document.querySelectorAll("[data-close-cart]").forEach((button) => {
    button.addEventListener("click", () => closeDrawer(dom.cartDrawer));
  });

  document.querySelector("[data-open-menu]").addEventListener("click", () => openDrawer(dom.menuDrawer));
  document.querySelector("[data-close-menu]").addEventListener("click", () => closeDrawer(dom.menuDrawer));

  document.querySelector("[data-open-search]").addEventListener("click", openSearch);
  document.querySelector("[data-close-search]").addEventListener("click", closeSearch);
  document.querySelector("[data-search-form]").addEventListener("submit", (event) => {
    event.preventDefault();
    const query = document.querySelector("#site-search").value.trim().toLowerCase();
    runSearch(query);
  });
  document.querySelector("#site-search").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    runSearch(query);
  });

  dom.overlay.addEventListener("click", closeAllOverlays);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllOverlays();
      closeMediaModal();
      closeSearch();
      closeReviewModal();
      closeProfileModal();
    }
    if (dom.mediaModal.classList.contains("is-active") && event.key === "ArrowRight") {
      moveMedia(1);
    }
    if (dom.mediaModal.classList.contains("is-active") && event.key === "ArrowLeft") {
      moveMedia(-1);
    }
  });

  document.querySelector("[data-feature-prev]").addEventListener("click", () => scrollFeatures(-1));
  document.querySelector("[data-feature-next]").addEventListener("click", () => scrollFeatures(1));
  dom.featureTrack.addEventListener("scroll", updateFeatureCounter, { passive: true });

  document.querySelector("[data-scroll-reviews]").addEventListener("click", () => {
    document.querySelector("#reviews").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.querySelector("[data-pickup-refresh]").addEventListener("click", async () => {
    try {
      const data = await apiRequest("/api/pickup");
      showToast(data.message || "Teslimat bilgisi güncellendi.");
    } catch {
      showToast("Teslimat bilgisi şu an güncellenemiyor.");
    }
  });

  document.querySelector("[data-share]").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      showToast("Bağlantı kopyalandı");
    } catch {
      showToast("Bağlantı paylaşmaya hazır.");
    }
  });

  document.querySelector("[data-checkout]").addEventListener("click", () => {
    startCheckout();
  });

  document.querySelector("[data-buy-now]").addEventListener("click", () => {
    startCheckout([buildCartItem(state.quantity)]);
  });

  document.querySelector("[data-review-filter]").addEventListener("click", () => {
    showToast("Filtre seçenekleri burada açılır.");
  });

  document.querySelector("[data-open-review-form]").addEventListener("click", openReviewModal);
  document.querySelector("[data-close-review-form]").addEventListener("click", closeReviewModal);
  dom.reviewForm.addEventListener("submit", submitReview);
  document.querySelector("[data-close-profile]").addEventListener("click", closeProfileModal);
  dom.profileModal.addEventListener("click", (event) => {
    if (event.target === dom.profileModal) closeProfileModal();
  });
  dom.reviewList.addEventListener("click", (event) => {
    const author = event.target.closest("[data-profile-image]");
    if (!author) return;
    openProfileModal(author.dataset.profileImage, author.dataset.profileName || author.textContent.trim());
  });

  document.querySelector("[data-review-sort]").addEventListener("change", (event) => {
    showToast(`${event.target.value} seçildi`);
  });

  document.querySelector("[data-review-media-next]")?.addEventListener("click", () => {
    const strip = document.querySelector("[data-review-media-strip]");
    if (!strip) return;
    const firstItem = strip.querySelector("button");
    const step = firstItem ? firstItem.getBoundingClientRect().width + 6 : 140;
    const atEnd = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 4;
    strip.scrollBy({ left: atEnd ? -strip.scrollWidth : step * 2, behavior: "smooth" });
  });

  document.querySelectorAll("[data-newsletter]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitNewsletter(form);
    });
  });

  document.querySelectorAll("[data-mega-trigger]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const item = trigger.closest(".nav-item");
      document.querySelectorAll(".nav-item.is-open").forEach((openItem) => {
        if (openItem !== item) openItem.classList.remove("is-open");
      });
      item.classList.toggle("is-open");
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".nav-item")) {
      document.querySelectorAll(".nav-item.is-open").forEach((item) => item.classList.remove("is-open"));
    }
  });
}

function syncFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const variantId = params.get("variant");
  const match = variants.find((item) => item.id === variantId);
  if (match) {
    setVariant(match.key, false);
  }
}

async function hydratePricing(options = {}) {
  if (state.pricingRequestInFlight) return;
  state.pricingRequestInFlight = true;
  try {
    const pricing = await apiRequest("/api/pricing");
    applyPricing(pricing, options);
  } catch {
    applyPricing(state.pricing, options);
  } finally {
    state.pricingRequestInFlight = false;
  }
}

function startPricingRefresh() {
  window.setInterval(() => hydratePricing({ animateDisplay: true }), PRICE_REFRESH_INTERVAL_MS);
}

function applyPricing(pricing, options = {}) {
  const previousPrice = Number(state.displayPricing?.productPrice ?? state.pricing?.productPrice);
  state.pricing = {
    ...fallbackPricing(),
    ...pricing
  };
  state.displayPricing = options.animateDisplay ? nextDisplayPricing(state.pricing) : state.pricing;
  const nextPrice = Number(state.displayPricing.productPrice);
  const priceDirection = getPriceDirection(previousPrice, nextPrice);
  const livePrice = Number(state.pricing.productPrice);
  state.cart = state.cart.map((item) => ({
    ...item,
    price: Number.isFinite(livePrice) ? livePrice : item.price,
    priceUsd: PRODUCT_PRICE_USD,
    currency: "TRY",
    exchangeRate: state.pricing.usdTryRate
  }));
  saveCart();
  renderPricing();
  if (state.pricingHasSynced && priceDirection) {
    flashPrice(priceDirection);
  }
  state.pricingHasSynced = true;
  renderCart();
}

function nextDisplayPricing(realPricing) {
  const baseRate = Number(realPricing.usdTryRate) || FALLBACK_USD_TRY_RATE;
  const previousRate = Number(state.displayPricing?.usdTryRate) || baseRate;
  let drift = clamp(previousRate - baseRate, -DISPLAY_RATE_DRIFT_LIMIT, DISPLAY_RATE_DRIFT_LIMIT);
  if (Math.abs(drift) > DISPLAY_RATE_DRIFT_LIMIT * 0.8) {
    state.priceTickDirection = -Math.sign(drift);
  } else if (Math.random() < 0.35) {
    state.priceTickDirection *= -1;
  }
  const step = 0.055 + Math.random() * 0.06;
  drift = clamp(drift + state.priceTickDirection * step, -DISPLAY_RATE_DRIFT_LIMIT, DISPLAY_RATE_DRIFT_LIMIT);
  const displayRate = baseRate + drift;
  return {
    ...realPricing,
    usdTryRate: displayRate,
    productPrice: roundMoney(PRODUCT_PRICE_USD * displayRate)
  };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getPriceDirection(previousPrice, nextPrice) {
  if (!Number.isFinite(previousPrice) || !Number.isFinite(nextPrice)) return "";
  const previous = Math.round(previousPrice * 100);
  const next = Math.round(nextPrice * 100);
  if (next > previous) return "up";
  if (next < previous) return "down";
  return "";
}

function fallbackPricing() {
  const productPrice = PRODUCT_PRICE_USD * FALLBACK_USD_TRY_RATE;
  return {
    baseCurrency: "USD",
    currency: "TRY",
    productPriceUsd: PRODUCT_PRICE_USD,
    productPrice,
    productPriceFormatted: formatMoney(productPrice),
    usdTryRate: FALLBACK_USD_TRY_RATE,
    usdTryRateFormatted: FALLBACK_USD_TRY_RATE.toFixed(4),
    rateSource: "fallback",
    installmentThreshold: 35 * FALLBACK_USD_TRY_RATE,
    installmentThresholdFormatted: formatMoney(35 * FALLBACK_USD_TRY_RATE),
    freeShippingThreshold: 50 * FALLBACK_USD_TRY_RATE,
    freeShippingThresholdFormatted: formatMoney(50 * FALLBACK_USD_TRY_RATE)
  };
}

function renderPricing() {
  const pricing = state.pricing;
  const displayPricing = state.displayPricing || pricing;
  dom.productPriceTry.textContent = formatMoney(displayPricing.productPrice);
  dom.productPriceUsd.textContent = `(${formatUsd(pricing.productPriceUsd)})`;
  dom.salePrice.textContent = formatMoney(displayPricing.productPrice);
  dom.installmentThreshold.textContent = formatMoney(pricing.installmentThreshold);
  dom.freeShippingThresholds.forEach((item) => {
    item.textContent = formatMoney(pricing.freeShippingThreshold);
  });
  dom.fxRate.textContent = `Canlı kur: 1 USD = ${formatRate(displayPricing.usdTryRate)} TL`;
  dom.relatedPrices.forEach((item) => {
    const usd = Number(item.dataset.relatedPrice);
    if (!Number.isFinite(usd)) return;
    const price = usd * Number(pricing.usdTryRate || FALLBACK_USD_TRY_RATE);
    const prefix = item.dataset.relatedPrefix;
    item.textContent = prefix ? `${prefix} ${formatMoney(price)}` : formatMoney(price);
  });
}

function flashPrice(direction) {
  dom.productPriceTry.classList.remove("is-up", "is-down");
  void dom.productPriceTry.offsetWidth;
  dom.productPriceTry.classList.add(direction === "up" ? "is-up" : "is-down");
  window.clearTimeout(flashPrice.timeout);
  flashPrice.timeout = window.setTimeout(() => {
    dom.productPriceTry.classList.remove("is-up", "is-down");
  }, 1000);
}

function renderThumbnails() {
  const visibleImages = getVariantImages();
  dom.mediaTotal.textContent = String(visibleImages.length);
  dom.modalTotal.textContent = String(visibleImages.length);
  dom.thumbnails.innerHTML = visibleImages.slice(1).map((image) => `
    <button class="thumb-button" type="button" data-thumb="${image.index}" aria-label="Görsel ${image.number}">
      <img src="${image.src}" alt="">
    </button>
  `).join("");

  dom.thumbnails.querySelectorAll("[data-thumb]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedImageIndex = Number(button.dataset.thumb);
      renderMedia();
    });
  });
}

function renderStyleOptions() {
  dom.styleOptions.innerHTML = styleOptions.map((option, index) => {
    const isActive = option.variantKey === state.selectedVariant.key;
    const classes = [
      "style-option",
      isActive ? "is-active" : "",
      option.available === false ? "is-unavailable" : ""
    ].filter(Boolean).join(" ");
    return `
      <button class="${classes}" type="button" data-style="${index}" aria-label="${escapeHtml(option.label)}${option.available === false ? " şu an stokta yok" : ""}">
        <img src="${option.image}" alt="">
        <span class="tooltip">${escapeHtml(option.label)}${option.available === false ? " şu an stokta yok" : ""}</span>
      </button>
    `;
  }).join("");

  dom.styleOptions.querySelectorAll("[data-style]").forEach((button) => {
    button.addEventListener("click", () => {
      const option = styleOptions[Number(button.dataset.style)];
      if (option.available === false) {
        showToast(`${option.label} şu an stokta yok.`);
        return;
      }
      if (option.variantKey) {
        setVariant(option.variantKey, true);
        return;
      }
      showToast(`${option.label} ayrı bir ürün sayfasında açılır.`);
    });
  });
}

function setVariant(key, updateUrl) {
  const variant = variants.find((item) => item.key === key);
  if (!variant) return;
  state.selectedVariant = variant;
  state.selectedImageIndex = variant.start - 1;
  renderThumbnails();
  renderMedia();
  renderStyleOptions();
  syncVariantMeta(updateUrl);
}

function syncVariantMeta(updateUrl) {
  dom.sku.textContent = state.selectedVariant.sku;
  if (updateUrl && window.history?.replaceState) {
    const url = new URL(window.location.href);
    url.searchParams.set("variant", state.selectedVariant.id);
    window.history.replaceState({}, "", url);
  }
}

function renderMedia() {
  const current = allImages[state.selectedImageIndex];
  const visibleImages = getVariantImages();
  const position = visibleImages.findIndex((image) => image.index === state.selectedImageIndex);
  dom.mainMedia.src = current.src;
  dom.mainMedia.alt = current.alt;
  dom.modalImage.src = current.src;
  dom.modalImage.alt = current.alt;
  dom.mediaCurrent.textContent = String(Math.max(1, position + 1));
  dom.modalCurrent.textContent = String(Math.max(1, position + 1));
  dom.mediaTotal.textContent = String(visibleImages.length);
  dom.modalTotal.textContent = String(visibleImages.length);

  dom.thumbnails.querySelectorAll("[data-thumb]").forEach((button) => {
    button.classList.toggle("is-active", Number(button.dataset.thumb) === state.selectedImageIndex);
  });
}

function moveMedia(direction) {
  const visibleImages = getVariantImages();
  const currentPosition = Math.max(0, visibleImages.findIndex((image) => image.index === state.selectedImageIndex));
  const nextPosition = (currentPosition + direction + visibleImages.length) % visibleImages.length;
  state.selectedImageIndex = visibleImages[nextPosition].index;
  renderMedia();
}

function getVariantImages() {
  return allImages.filter((image) => image.variantKey === state.selectedVariant.key);
}

function openMediaModal() {
  dom.mediaModal.classList.add("is-active");
  dom.mediaModal.setAttribute("aria-hidden", "false");
  dom.body.classList.add("drawer-open");
}

function closeMediaModal() {
  dom.mediaModal.classList.remove("is-active");
  dom.mediaModal.setAttribute("aria-hidden", "true");
  if (!dom.overlay.classList.contains("is-active") && !dom.searchModal.classList.contains("is-active") && !dom.profileModal.classList.contains("is-active")) {
    dom.body.classList.remove("drawer-open");
  }
}

function setQuantity(value) {
  state.quantity = Math.max(1, Number.isFinite(value) ? Math.floor(value) : 1);
  dom.quantity.value = String(state.quantity);
}

async function addToCart() {
  const item = buildCartItem(state.quantity);
  try {
    const data = await apiRequest("/api/cart/add", {
      method: "POST",
      body: {
        sessionId: state.sessionId,
        variantKey: item.key,
        quantity: item.quantity
      }
    });
    applyBackendCart(data.cart);
  } catch {
    addLocalCartItem(item);
  }
  saveCart();
  renderCart();
  openDrawer(dom.cartDrawer);
}

function buildCartItem(quantity) {
  return {
    key: state.selectedVariant.key,
    id: state.selectedVariant.id,
    name: state.selectedVariant.name,
    sku: state.selectedVariant.sku,
    image: allImages[state.selectedVariant.start - 1].src,
    price: state.pricing.productPrice,
    priceUsd: PRODUCT_PRICE_USD,
    currency: "TRY",
    exchangeRate: state.pricing.usdTryRate,
    quantity: Math.max(1, quantity)
  };
}

function addLocalCartItem(item) {
  const existing = state.cart.find((cartItem) => cartItem.key === item.key);
  if (existing) {
    existing.quantity += item.quantity;
  } else {
    state.cart.push(item);
  }
}

function renderCart() {
  const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  const total = state.cart.reduce((sum, item) => sum + item.quantity * item.price, 0);
  dom.cartCount.textContent = String(count);
  dom.cartCount.hidden = count === 0;
  dom.cartEmpty.hidden = count > 0;
  dom.cartFilled.hidden = count === 0;
  dom.cartTotal.textContent = formatMoney(total);

  dom.cartItems.innerHTML = state.cart.map((item) => `
    <article class="cart-item" data-cart-key="${item.key}">
      <img src="${item.image}" alt="">
      <div>
        <h3>Fresh Pop Mısır Patlatma Makinesi</h3>
        <p>${escapeHtml(item.name)}</p>
        <p>${item.quantity} x ${formatMoney(item.price)}</p>
        <div class="cart-actions">
          <strong>${formatMoney(item.quantity * item.price)}</strong>
          <button type="button" data-remove-cart="${item.key}">Kaldır</button>
        </div>
      </div>
    </article>
  `).join("");

  dom.cartItems.querySelectorAll("[data-remove-cart]").forEach((button) => {
    button.addEventListener("click", () => {
      removeCartItem(button.dataset.removeCart);
    });
  });
}

async function removeCartItem(key) {
  try {
    const data = await apiRequest("/api/cart/remove", {
      method: "POST",
      body: {
        sessionId: state.sessionId,
        key
      }
    });
    applyBackendCart(data.cart);
  } catch {
    state.cart = state.cart.filter((item) => item.key !== key);
  }
  saveCart();
  renderCart();
}

function openDrawer(drawer) {
  closeSearch();
  dom.overlay.classList.add("is-active");
  drawer.classList.add("is-active");
  drawer.setAttribute("aria-hidden", "false");
  dom.body.classList.add("drawer-open");
}

function closeDrawer(drawer) {
  drawer.classList.remove("is-active");
  drawer.setAttribute("aria-hidden", "true");
  if (![dom.cartDrawer, dom.menuDrawer].some((item) => item.classList.contains("is-active"))) {
    dom.overlay.classList.remove("is-active");
    if (!dom.mediaModal.classList.contains("is-active") && !dom.searchModal.classList.contains("is-active")) {
      dom.body.classList.remove("drawer-open");
    }
  }
}

function closeAllOverlays() {
  closeDrawer(dom.cartDrawer);
  closeDrawer(dom.menuDrawer);
}

function openSearch() {
  closeAllOverlays();
  dom.searchModal.classList.add("is-active");
  dom.searchModal.setAttribute("aria-hidden", "false");
  dom.body.classList.add("drawer-open");
  setTimeout(() => document.querySelector("#site-search").focus(), 80);
}

function closeSearch() {
  dom.searchModal.classList.remove("is-active");
  dom.searchModal.setAttribute("aria-hidden", "true");
  if (!dom.mediaModal.classList.contains("is-active") && !dom.overlay.classList.contains("is-active") && !dom.profileModal.classList.contains("is-active")) {
    dom.body.classList.remove("drawer-open");
  }
}

function renderSearchResults(items) {
  const list = items.length ? items : ["Sonuç bulunamadı"];
  dom.searchResults.innerHTML = list.map((item) => `<a href="#">${escapeHtml(item)}</a>`).join("");
}

function scrollFeatures(direction) {
  const card = dom.featureTrack.querySelector("article");
  if (!card) return;
  const amount = card.getBoundingClientRect().width + getFeatureGap();
  dom.featureTrack.scrollBy({ left: amount * direction, behavior: "smooth" });
}

function updateFeatureCounter() {
  const card = dom.featureTrack.querySelector("article");
  if (!card) return;
  const amount = card.getBoundingClientRect().width + getFeatureGap();
  const index = Math.round(dom.featureTrack.scrollLeft / amount);
  state.featureIndex = Math.min(5, Math.max(0, index));
  dom.featureCurrent.textContent = String(state.featureIndex + 1);
}

function getFeatureGap() {
  const styles = window.getComputedStyle(dom.featureTrack);
  return parseFloat(styles.columnGap || styles.gap || "0") || 0;
}

async function hydrateBackendCart() {
  try {
    const data = await apiRequest(`/api/cart?session=${encodeURIComponent(state.sessionId)}`);
    applyBackendCart(data.cart);
    saveCart();
    renderCart();
  } catch {
    state.backendReady = false;
  }
}

function applyBackendCart(cart) {
  if (!cart || !Array.isArray(cart.items)) return;
  state.backendReady = true;
  state.cart = cart.items.map((item) => ({
    ...item,
    price: item.currency === "TRY" ? Number(item.price) || state.pricing.productPrice : state.pricing.productPrice,
    priceUsd: item.priceUsd || PRODUCT_PRICE_USD,
    currency: item.currency || "TRY",
    exchangeRate: item.exchangeRate || state.pricing.usdTryRate
  }));
}

async function startCheckout(items = null) {
  const checkoutItems = items || state.cart;
  if (!checkoutItems.length) {
    showToast("Sepetiniz boş.");
    return;
  }
  try {
    const data = await apiRequest("/api/checkout", {
      method: "POST",
      body: {
        sessionId: state.sessionId,
        items: items || undefined
      }
    });
    if (data.redirectUrl) {
      window.location.href = data.redirectUrl;
      return;
    }
    showToast(data.message || "iyzico ödeme sayfası hazır.");
  } catch {
    showToast("Ödeme sayfasına şu an ulaşılamıyor.");
  }
}

async function submitNewsletter(form) {
  const input = form.querySelector("input[type='email']");
  const email = input?.value.trim();
  if (!email) {
    showToast("E-posta adresinizi girin.");
    return;
  }
  try {
    const data = await apiRequest("/api/newsletter", {
      method: "POST",
      body: { email }
    });
    input.value = "";
    showToast(data.message || "E-posta adresiniz kaydedildi.");
  } catch {
    showToast("Şu an e-posta adresinizi kaydedemiyoruz.");
  }
}

async function runSearch(query) {
  try {
    const data = await apiRequest(`/api/search?q=${encodeURIComponent(query)}`);
    renderSearchResults(data.items || []);
  } catch {
    renderSearchResults(query ? searchItems.filter((item) => item.toLowerCase().includes(query)) : searchItems);
  }
}

async function apiRequest(path, options = {}) {
  let lastError;
  for (const base of API_BASES) {
    try {
      const response = await fetch(`${base}${path}`, {
        method: options.method || "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Dash-Session": state.sessionId
        },
        body: options.body ? JSON.stringify(options.body) : undefined
      });
      const text = await response.text();
      const data = JSON.parse(text);
      if (!response.ok) {
        throw new Error(data.error || "API request failed");
      }
      return data;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("API request failed");
}

function openReviewModal() {
  dom.reviewModal.classList.add("is-active");
  dom.reviewModal.setAttribute("aria-hidden", "false");
  dom.body.classList.add("drawer-open");
  setTimeout(() => dom.reviewForm.querySelector("input")?.focus(), 80);
}

function closeReviewModal() {
  dom.reviewModal.classList.remove("is-active");
  dom.reviewModal.setAttribute("aria-hidden", "true");
  if (!dom.mediaModal.classList.contains("is-active") && !dom.overlay.classList.contains("is-active") && !dom.searchModal.classList.contains("is-active") && !dom.profileModal.classList.contains("is-active")) {
    dom.body.classList.remove("drawer-open");
  }
}

function openProfileModal(src, name) {
  if (!src) return;
  dom.profileModalImage.src = src;
  dom.profileModalImage.alt = `${name} profil fotoğrafı`;
  dom.profileModalName.textContent = name;
  dom.profileModal.classList.add("is-active");
  dom.profileModal.setAttribute("aria-hidden", "false");
  dom.body.classList.add("drawer-open");
}

function closeProfileModal() {
  dom.profileModal.classList.remove("is-active");
  dom.profileModal.setAttribute("aria-hidden", "true");
  if (!dom.mediaModal.classList.contains("is-active") && !dom.overlay.classList.contains("is-active") && !dom.searchModal.classList.contains("is-active") && !dom.reviewModal.classList.contains("is-active")) {
    dom.body.classList.remove("drawer-open");
  }
}

async function submitReview(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
    name: formData.get("name"),
    email: formData.get("email"),
    rating: Number(formData.get("rating")),
    title: formData.get("title"),
    body: formData.get("body"),
    variantName: state.selectedVariant.name
  };

  try {
    const data = await apiRequest("/api/reviews", {
      method: "POST",
      body: payload
    });
    prependReview(data.review);
    showToast(data.message || "Yorumunuz kaydedildi.");
  } catch {
    prependReview({
      ...payload,
      product: "Fresh Pop Mısır Patlatma Makinesi",
      verified: false,
      createdAt: Math.floor(Date.now() / 1000)
    });
    showToast("Yorumunuz bu oturum için eklendi.");
  }

  form.reset();
  closeReviewModal();
}

function prependReview(review) {
  if (!dom.reviewList || !review) return;
  dom.reviewList.insertAdjacentHTML("afterbegin", renderReviewArticle(review));
}

function renderReviewArticle(review) {
  const rating = Math.max(1, Math.min(5, Number(review.rating) || 5));
  const stars = "★".repeat(rating) + "☆".repeat(5 - rating);
  return `
    <article>
      <aside>
        <div class="review-author">
          <span class="review-avatar" aria-hidden="true">${escapeHtml(getInitials(review.name || "Müşteri"))}</span>
          <strong>${escapeHtml(review.name || "Müşteri")}</strong>
        </div>
        <span class="${review.verified ? "verified" : "review-status"}">${review.verified ? "Ürünü satın aldı" : "Yeni yorum"}</span>
        <div class="review-product">
          <img src="${allImages[state.selectedVariant.start - 1].src}" alt="">
          <div>
            <span class="reviewing">Değerlendirilen ürün</span>
            <a href="#">${escapeHtml(review.product || "Fresh Pop Mısır Patlatma Makinesi")}</a>
          </div>
        </div>
        <p>Bu ürünü tavsiye ederim.</p>
      </aside>
      <div class="review-content">
        <div class="review-stars" aria-label="5 üzerinden ${rating} yıldız">${stars}</div>
        <time datetime="">az önce</time>
        <h3>${escapeHtml(review.title || "")}</h3>
        <p>${escapeHtml(review.body || "")}</p>
        <button type="button">Devamını oku</button>
        <small>Bu değerlendirme faydalı mı? <span>Evet 0</span> <span>Hayır 0</span></small>
      </div>
    </article>
  `;
}

function getSessionId() {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const value = `sess_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(SESSION_STORAGE_KEY, value);
  return value;
}

function getInitials(name) {
  return String(name)
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toLocaleUpperCase("tr-TR") || "M";
}

function loadCart() {
  try {
    return JSON.parse(localStorage.getItem("dash-cart") || "[]");
  } catch {
    return [];
  }
}

function saveCart() {
  localStorage.setItem("dash-cart", JSON.stringify(state.cart));
}

function roundMoney(value) {
  return Math.round((Number(value) || 0) * 100) / 100;
}

function formatMoney(value) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(Number(value) || 0);
}

function formatUsd(value) {
  return `${(Number(value) || PRODUCT_PRICE_USD).toFixed(2)}$`;
}

function formatRate(value) {
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(Number(value) || FALLBACK_USD_TRY_RATE);
}

function showToast(message) {
  dom.toast.textContent = message;
  dom.toast.classList.add("is-active");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    dom.toast.classList.remove("is-active");
  }, 2600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
