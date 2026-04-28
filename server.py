from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import time
import uuid
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / ".data")).expanduser()
DB_PATH = DATA_DIR / "store.json"
DB_LOCK = Lock()

PRODUCT_PRICE_USD = 34.99
FREE_SHIPPING_THRESHOLD_USD = 50
INSTALLMENT_THRESHOLD_USD = 35
SHIPPING_USD = 6.95
FALLBACK_USD_TRY_RATE = float(os.environ.get("FALLBACK_USD_TRY_RATE", "45.0"))
FX_CACHE_SECONDS = int(os.environ.get("FX_CACHE_SECONDS", "4"))
FX_CACHE: dict[str, object] = {"rate": FALLBACK_USD_TRY_RATE, "source": "fallback", "timestamp": 0}
DISCOUNT_CODES = {
    "BURCU20": {
        "rate": 0.20,
        "label": "BURCU20",
        "message": "BURCU20 kodu uygulandı. %20 indirim toplamdan düşüldü.",
    }
}

VARIANTS = [
    {
        "key": "winnie",
        "id": "44802965635126",
        "name": "Winnie The Pooh",
        "sku": "DAPP15009",
        "image": "assets/products/product-01.jpg",
        "available": True,
    },
    {
        "key": "toy-story",
        "id": "44936477081654",
        "name": "Toy Story",
        "sku": "DAPP15008",
        "image": "assets/products/product-27.jpg",
        "available": True,
    },
    {
        "key": "moana",
        "id": "45066779197494",
        "name": "Moana",
        "sku": "DAPP15007",
        "image": "assets/products/product-37.jpg",
        "available": True,
    },
    {
        "key": "mickey-minnie",
        "id": "44094983012406",
        "name": "Mickey & Minnie",
        "sku": "DDYAP150CM4",
        "image": "assets/products/product-09.jpg",
        "available": True,
    },
    {
        "key": "princess",
        "id": "44161061027894",
        "name": "Prenses",
        "sku": "DDYAP1503PK4",
        "image": "assets/products/product-15.jpg",
        "available": True,
    },
    {
        "key": "stitch",
        "id": "44094983077942",
        "name": "Stitch",
        "sku": "DDYAP1502BU4",
        "image": "assets/products/product-21.jpg",
        "available": True,
    },
]

SEARCH_ITEMS = [
    "Mısır Patlatma Makineleri",
    "Çok Amaçlı Makineler",
    "Dondurma Makineleri",
    "Disney | Dash",
    "Peanuts x Dash",
    "Waffle Makineleri",
    "Air Fryer",
    "Fresh Pop Mısır Patlatma Makinesi",
]


def initial_db() -> dict:
    return {
        "sessions": {},
        "newsletter": [],
        "orders": [],
        "reviews": [],
    }


def load_db() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        save_db(initial_db())
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = DATA_DIR / f"store-broken-{int(time.time())}.json"
        DB_PATH.replace(backup)
        db = initial_db()
        save_db(db)
        return db


def save_db(db: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp_path = DB_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(DB_PATH)


def find_variant(value: str | None) -> dict | None:
    if not value:
        return None
    return next((item for item in VARIANTS if item["key"] == value or item["id"] == value), None)


def clamp_quantity(value: object) -> int:
    try:
        return max(1, min(20, int(value)))
    except (TypeError, ValueError):
        return 1


def money(value: float) -> float:
    return round(value + 0.0000001, 2)


def format_try(value: float) -> str:
    formatted = f"{money(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"₺{formatted}"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "bydash-localization/1.0"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def get_usd_try_rate() -> dict:
    now = time.time()
    if now - float(FX_CACHE.get("timestamp") or 0) < FX_CACHE_SECONDS:
        return dict(FX_CACHE)

    sources = [
        ("open.er-api.com", "https://open.er-api.com/v6/latest/USD"),
        ("frankfurter.app", "https://api.frankfurter.app/latest?from=USD&to=TRY"),
    ]
    for source, url in sources:
        try:
            data = fetch_json(url)
            rate = float((data.get("rates") or {}).get("TRY"))
            if rate > 0:
                FX_CACHE.update({
                    "rate": rate,
                    "source": source,
                    "timestamp": now,
                    "updatedAt": data.get("time_last_update_utc") or data.get("date"),
                })
                return dict(FX_CACHE)
        except Exception:
            continue

    FX_CACHE["timestamp"] = now
    return dict(FX_CACHE)


def price_try(usd_value: float, rate: float | None = None) -> float:
    return money(usd_value * (rate or float(get_usd_try_rate()["rate"])))


def normalize_discount_code(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def discount_for_code(value: object) -> dict | None:
    return DISCOUNT_CODES.get(normalize_discount_code(value))


def pricing_payload() -> dict:
    fx = get_usd_try_rate()
    rate = float(fx["rate"])
    product_try = price_try(PRODUCT_PRICE_USD, rate)
    return {
        "baseCurrency": "USD",
        "currency": "TRY",
        "productPriceUsd": PRODUCT_PRICE_USD,
        "productPrice": product_try,
        "productPriceFormatted": format_try(product_try),
        "usdTryRate": rate,
        "usdTryRateFormatted": f"{rate:.4f}",
        "rateSource": fx.get("source"),
        "rateUpdatedAt": fx.get("updatedAt"),
        "installmentThreshold": price_try(INSTALLMENT_THRESHOLD_USD, rate),
        "installmentThresholdFormatted": format_try(price_try(INSTALLMENT_THRESHOLD_USD, rate)),
        "freeShippingThreshold": price_try(FREE_SHIPPING_THRESHOLD_USD, rate),
        "freeShippingThresholdFormatted": format_try(price_try(FREE_SHIPPING_THRESHOLD_USD, rate)),
    }


def cart_payload(items: list[dict], discount_code: str | None = None) -> dict:
    pricing = pricing_payload()
    for item in items:
        item["price"] = pricing["productPrice"]
        item["priceUsd"] = PRODUCT_PRICE_USD
        item["currency"] = "TRY"
        item["exchangeRate"] = pricing["usdTryRate"]
    subtotal = money(sum(item["price"] * item["quantity"] for item in items))
    free_shipping_threshold = pricing["freeShippingThreshold"]
    discount = discount_for_code(discount_code)
    discount_amount = money(subtotal * discount["rate"]) if discount else 0
    discounted_subtotal = money(max(0, subtotal - discount_amount))
    shipping = 0 if discounted_subtotal >= free_shipping_threshold or subtotal == 0 else price_try(SHIPPING_USD, pricing["usdTryRate"])
    tax = 0
    total = money(discounted_subtotal + shipping + tax)
    return {
        "items": items,
        "summary": {
            "currency": "TRY",
            "subtotal": subtotal,
            "discount": discount_amount,
            "discountCode": discount["label"] if discount else "",
            "discountRate": discount["rate"] if discount else 0,
            "shipping": money(shipping),
            "tax": tax,
            "total": total,
            "freeShippingThreshold": free_shipping_threshold,
            "exchangeRate": pricing["usdTryRate"],
            "exchangeRateSource": pricing["rateSource"],
        },
    }


def session_cart(db: dict, session_id: str) -> list[dict]:
    session = db["sessions"].setdefault(session_id, {"cart": []})
    return session.setdefault("cart", [])


def make_cart_item(variant: dict, quantity: int) -> dict:
    pricing = pricing_payload()
    return {
        "key": variant["key"],
        "id": variant["id"],
        "name": variant["name"],
        "sku": variant["sku"],
        "image": variant["image"],
        "price": pricing["productPrice"],
        "priceUsd": PRODUCT_PRICE_USD,
        "currency": "TRY",
        "exchangeRate": pricing["usdTryRate"],
        "quantity": quantity,
    }


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


class DashHandler(BaseHTTPRequestHandler):
    server_version = "DashLocalBackend/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_get_api(parsed)
            return
        if parsed.path.startswith("/checkout/"):
            self.render_checkout(parsed.path.rsplit("/", 1)[-1])
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_post_api(parsed)
            return
        self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def handle_get_api(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            self.respond_json({"ok": True, "service": "dash-local-backend"})
            return
        if parsed.path == "/api/catalog":
            pricing = pricing_payload()
            self.respond_json({
                "price": pricing["productPrice"],
                "pricing": pricing,
                "variants": VARIANTS,
                "searchItems": SEARCH_ITEMS,
            })
            return
        if parsed.path == "/api/pricing":
            self.respond_json(pricing_payload())
            return
        if parsed.path == "/api/search":
            term = (query.get("q", [""])[0] or "").strip().lower()
            items = SEARCH_ITEMS
            if term:
                items = [item for item in SEARCH_ITEMS if term in item.lower()]
            self.respond_json({"items": items})
            return
        if parsed.path == "/api/cart":
            session_id = self.session_id(query)
            with DB_LOCK:
                db = load_db()
                payload = cart_payload(session_cart(db, session_id))
                save_db(db)
            self.respond_json({"sessionId": session_id, "cart": payload})
            return
        if parsed.path == "/api/reviews":
            with DB_LOCK:
                db = load_db()
                reviews = list(reversed(db.get("reviews", [])))
            self.respond_json({"reviews": reviews})
            return
        if parsed.path == "/api/pickup":
            self.respond_json({
                "available": True,
                "message": "Kargo ve teslimat seçenekleri ödeme adımında netleşir.",
                "estimatedDispatch": "1-2 iş günü",
            })
            return
        self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def handle_post_api(self, parsed) -> None:
        body = self.read_json()
        if parsed.path == "/api/cart/add":
            self.add_to_cart(body)
            return
        if parsed.path == "/api/cart/remove":
            self.remove_from_cart(body)
            return
        if parsed.path == "/api/cart/clear":
            self.clear_cart(body)
            return
        if parsed.path == "/api/checkout":
            self.create_checkout(body)
            return
        if parsed.path == "/api/newsletter":
            self.create_newsletter_signup(body)
            return
        if parsed.path == "/api/reviews":
            self.create_review(body)
            return
        match = re.fullmatch(r"/api/orders/([^/]+)/discount", parsed.path)
        if match:
            self.apply_order_discount(match.group(1), body)
            return
        match = re.fullmatch(r"/api/orders/([^/]+)/pay", parsed.path)
        if match:
            self.mark_order_paid(match.group(1))
            return
        self.respond_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def add_to_cart(self, body: dict) -> None:
        session_id = str(body.get("sessionId") or self.headers.get("X-Dash-Session") or uuid.uuid4())
        variant = find_variant(body.get("variantKey") or body.get("variantId"))
        if not variant or not variant.get("available"):
            self.respond_json({"error": "Bu ürün şu an sepete eklenemiyor."}, HTTPStatus.BAD_REQUEST)
            return
        quantity = clamp_quantity(body.get("quantity"))
        with DB_LOCK:
            db = load_db()
            cart = session_cart(db, session_id)
            existing = next((item for item in cart if item["key"] == variant["key"]), None)
            if existing:
                existing["quantity"] = min(20, existing["quantity"] + quantity)
            else:
                cart.append(make_cart_item(variant, quantity))
            payload = cart_payload(cart)
            save_db(db)
        self.respond_json({"sessionId": session_id, "cart": payload})

    def remove_from_cart(self, body: dict) -> None:
        session_id = str(body.get("sessionId") or self.headers.get("X-Dash-Session") or "")
        key = str(body.get("key") or "")
        with DB_LOCK:
            db = load_db()
            cart = session_cart(db, session_id)
            db["sessions"][session_id]["cart"] = [item for item in cart if item["key"] != key]
            payload = cart_payload(db["sessions"][session_id]["cart"])
            save_db(db)
        self.respond_json({"sessionId": session_id, "cart": payload})

    def clear_cart(self, body: dict) -> None:
        session_id = str(body.get("sessionId") or self.headers.get("X-Dash-Session") or "")
        with DB_LOCK:
            db = load_db()
            db["sessions"].setdefault(session_id, {"cart": []})["cart"] = []
            payload = cart_payload([])
            save_db(db)
        self.respond_json({"sessionId": session_id, "cart": payload})

    def create_checkout(self, body: dict) -> None:
        session_id = str(body.get("sessionId") or self.headers.get("X-Dash-Session") or uuid.uuid4())
        with DB_LOCK:
            db = load_db()
            if body.get("items"):
                items = [self.normalize_checkout_item(item) for item in body["items"]]
                items = [item for item in items if item]
            else:
                items = list(session_cart(db, session_id))
            if not items:
                self.respond_json({"error": "Sepet boş."}, HTTPStatus.BAD_REQUEST)
                return
            summary = cart_payload(items)["summary"]
            order_id = f"TR-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
            order = {
                "id": order_id,
                "sessionId": session_id,
                "items": items,
                "summary": summary,
                "paymentProvider": "iyzico",
                "status": "payment_pending",
                "createdAt": int(time.time()),
            }
            db["orders"].append(order)
            save_db(db)
        self.respond_json({
            "order": order,
            "redirectUrl": f"http://{self.headers.get('Host', '127.0.0.1')}/checkout/{order_id}",
            "message": "iyzico ödeme sayfası hazır.",
        }, HTTPStatus.CREATED)

    def normalize_checkout_item(self, item: dict) -> dict | None:
        variant = find_variant(item.get("key") or item.get("id") or item.get("variantKey") or item.get("variantId"))
        if not variant:
            return None
        return make_cart_item(variant, clamp_quantity(item.get("quantity")))

    def create_newsletter_signup(self, body: dict) -> None:
        email = str(body.get("email") or "").strip().lower()
        if not valid_email(email):
            self.respond_json({"error": "Lütfen geçerli bir e-posta adresi girin."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK:
            db = load_db()
            existing = next((item for item in db["newsletter"] if item["email"] == email), None)
            if not existing:
                db["newsletter"].append({"email": email, "createdAt": int(time.time())})
                save_db(db)
        self.respond_json({"ok": True, "message": "E-posta adresiniz kaydedildi."}, HTTPStatus.CREATED)

    def create_review(self, body: dict) -> None:
        name = str(body.get("name") or "").strip()[:80]
        email = str(body.get("email") or "").strip().lower()
        title = str(body.get("title") or "").strip()[:120]
        text = str(body.get("body") or "").strip()[:1200]
        rating = clamp_quantity(body.get("rating"))
        rating = min(5, rating)
        if not name or not valid_email(email) or not title or len(text) < 12:
            self.respond_json({"error": "Yorum göndermek için ad, e-posta, başlık ve yorum metni gerekli."}, HTTPStatus.BAD_REQUEST)
            return
        review = {
            "id": uuid.uuid4().hex,
            "name": name,
            "email": email,
            "rating": rating,
            "title": title,
            "body": text,
            "verified": False,
            "product": "Fresh Pop Mısır Patlatma Makinesi",
            "variant": body.get("variantName") or "Winnie The Pooh",
            "createdAt": int(time.time()),
        }
        with DB_LOCK:
            db = load_db()
            db["reviews"].append(review)
            save_db(db)
        self.respond_json({"review": review, "message": "Yorumunuz kaydedildi."}, HTTPStatus.CREATED)

    def apply_order_discount(self, order_id: str, body: dict) -> None:
        code = normalize_discount_code(body.get("code"))
        discount = discount_for_code(code)
        if not discount:
            self.respond_json({"error": "Bu indirim kodu geçerli değil."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK:
            db = load_db()
            order = next((item for item in db["orders"] if item["id"] == order_id), None)
            if not order:
                self.respond_json({"error": "Sipariş bulunamadı."}, HTTPStatus.NOT_FOUND)
                return
            if order["status"] == "paid":
                self.respond_json({"error": "Ödemesi tamamlanan siparişte indirim kodu değiştirilemez."}, HTTPStatus.BAD_REQUEST)
                return
            order["summary"] = cart_payload(order["items"], code)["summary"]
            order["discountCode"] = discount["label"]
            save_db(db)
        self.respond_json({"order": order, "summary": order["summary"], "message": discount["message"]})

    def mark_order_paid(self, order_id: str) -> None:
        with DB_LOCK:
            db = load_db()
            order = next((item for item in db["orders"] if item["id"] == order_id), None)
            if not order:
                self.respond_json({"error": "Sipariş bulunamadı."}, HTTPStatus.NOT_FOUND)
                return
            order["status"] = "paid"
            order["paidAt"] = int(time.time())
            db["sessions"].setdefault(order["sessionId"], {"cart": []})["cart"] = []
            save_db(db)
        self.respond_json({"order": order, "message": "Ödeme başarıyla tamamlandı."})

    def render_checkout(self, order_id: str) -> None:
        order_id = unquote(order_id)
        with DB_LOCK:
            db = load_db()
            order = next((item for item in db["orders"] if item["id"] == order_id), None)
        if not order:
            self.send_error(HTTPStatus.NOT_FOUND, "Sipariş bulunamadı")
            return
        summary = order["summary"]
        currency = summary.get("currency", "TRY")

        def format_order_money(value: float) -> str:
            return format_try(value) if currency == "TRY" else f"${money(value):.2f}"

        discount_amount = float(summary.get("discount") or 0)
        discount_code = str(summary.get("discountCode") or "")
        discount_row_class = "" if discount_amount > 0 else "is-hidden"
        discount_label = f"İndirim ({escape(discount_code)})" if discount_code else "İndirim"
        discount_message = f"{escape(discount_code)} kodu uygulandı." if discount_code else "BURCU20 kodunu deneyin."
        rows = "\n".join(
            f"""
            <li class="checkout-item">
              <img src="/{escape(item.get('image', 'assets/products/product-01.jpg'))}" alt="">
              <div>
                <strong>{escape(item['name'])}</strong>
                <span>Fresh Pop Mısır Patlatma Makinesi</span>
                <small>Adet: {item['quantity']}</small>
              </div>
              <b>{format_order_money(item['price'] * item['quantity'])}</b>
            </li>"""
            for item in order["items"]
        )
        status = "Ödeme tamamlandı" if order["status"] == "paid" else "Ödeme bekleniyor"
        disabled = "disabled" if order["status"] == "paid" else ""
        page = f"""<!doctype html>
<html lang="tr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>iyzico Ödeme - {escape(order_id)}</title>
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin:0; font-family: Arial, sans-serif; color:#003847; background:linear-gradient(180deg,#eef7fa 0,#f8fcfd 48%,#fff 100%); }}
      a {{ color:#003847; text-underline-offset:3px; }}
      .checkout-shell {{ width:min(1120px, calc(100% - 32px)); margin:40px auto; }}
      .checkout-hero {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; margin-bottom:22px; }}
      .brand-row {{ display:flex; align-items:center; gap:12px; margin-bottom:16px; }}
      .badge {{ display:inline-flex; align-items:center; min-height:32px; padding:5px 13px 6px; background:#13a4d8; color:#fff; border-radius:999px; font-weight:800; letter-spacing:.01em; box-shadow:0 10px 22px rgba(19,164,216,.22); }}
      .secure {{ color:#426674; font-size:14px; margin:0; }}
      h1 {{ margin:0 0 8px; font-size:34px; line-height:1.05; }}
      h2 {{ margin:0 0 18px; font-size:18px; text-transform:uppercase; letter-spacing:.08em; }}
      .status {{ margin:0; padding:9px 14px; border:1px solid #c9e1e8; border-radius:999px; background:#fff; font-weight:700; color:#0b5368; }}
      .checkout-card {{ display:grid; grid-template-columns:minmax(0, 1.1fr) 420px; gap:22px; align-items:start; }}
      .panel {{ background:#fff; border:1px solid #d7e5ea; box-shadow:0 18px 42px rgba(0,56,71,.08); }}
      .order-panel {{ padding:28px; }}
      .payment-panel {{ position:sticky; top:20px; padding:28px; }}
      .order-meta {{ display:flex; justify-content:space-between; gap:16px; padding:14px 0 22px; color:#5f7a84; border-bottom:1px solid #d7e5ea; font-size:14px; }}
      .item-list {{ padding:0; list-style:none; margin:0; }}
      .checkout-item {{ display:grid; grid-template-columns:74px minmax(0, 1fr) auto; gap:16px; align-items:center; padding:18px 0; border-bottom:1px solid #e4eef2; }}
      .checkout-item img {{ width:74px; height:74px; object-fit:contain; border:1px solid #e0edf1; background:#f8fbfc; }}
      .checkout-item strong {{ display:block; font-size:16px; margin-bottom:5px; }}
      .checkout-item span, .checkout-item small {{ display:block; color:#5f7a84; }}
      .checkout-item b {{ font-size:16px; white-space:nowrap; }}
      .discount-form {{ margin-top:24px; padding:18px; border:1px solid #d7e5ea; background:#f7fbfc; }}
      .discount-form label {{ display:block; margin-bottom:9px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; font-size:12px; }}
      .discount-control {{ display:grid; grid-template-columns:1fr auto; gap:10px; }}
      .discount-control input {{ min-width:0; height:48px; padding:0 14px; border:1px solid #b9d2da; border-radius:999px; color:#003847; font:inherit; text-transform:uppercase; }}
      .discount-control button {{ width:auto; min-width:118px; height:48px; padding:0 18px; }}
      .discount-message {{ margin:10px 0 0; min-height:20px; color:#0b6f3a; font-size:13px; font-weight:700; }}
      .discount-message.is-error {{ color:#c32222; }}
      .payment-note {{ margin:0 0 20px; color:#5f7a84; line-height:1.6; }}
      .summary-list {{ display:grid; gap:12px; margin:22px 0; padding:20px 0; border-top:1px solid #d7e5ea; border-bottom:1px solid #d7e5ea; }}
      .summary-row {{ display:flex; justify-content:space-between; gap:18px; }}
      .summary-row span {{ color:#5f7a84; }}
      .summary-row strong {{ font-size:18px; }}
      .summary-row.discount {{ color:#0b8a45; font-weight:700; }}
      .summary-row.total {{ align-items:flex-end; padding-top:8px; }}
      .summary-row.total strong {{ font-size:28px; }}
      .is-hidden {{ display:none; }}
      button {{ width:100%; border:0; border-radius:999px; background:#13a4d8; color:#fff; padding:16px; font-weight:800; font-size:16px; cursor:pointer; transition:transform .16s ease, background .16s ease; }}
      button:hover {{ background:#078ec2; transform:translateY(-1px); }}
      button:disabled {{ opacity:.55; cursor:default; transform:none; }}
      .trust-list {{ display:grid; gap:9px; margin:18px 0 0; padding:0; list-style:none; color:#426674; font-size:13px; }}
      .trust-list li::before {{ content:"✓"; margin-right:8px; color:#0b8a45; font-weight:800; }}
      .back-link {{ display:inline-block; margin-top:22px; }}
      @media (max-width: 860px) {{
        .checkout-shell {{ margin:24px auto; }}
        .checkout-hero {{ display:block; }}
        .status {{ display:inline-block; margin-top:16px; }}
        .checkout-card {{ grid-template-columns:1fr; }}
        .payment-panel {{ position:static; }}
      }}
      @media (max-width: 560px) {{
        h1 {{ font-size:28px; }}
        .order-panel, .payment-panel {{ padding:20px; }}
        .checkout-item {{ grid-template-columns:62px 1fr; }}
        .checkout-item b {{ grid-column:2; }}
        .discount-control {{ grid-template-columns:1fr; }}
        .discount-control button {{ width:100%; }}
      }}
    </style>
  </head>
  <body>
    <main class="checkout-shell">
      <section class="checkout-hero">
        <div>
          <div class="brand-row"><span class="badge">iyzico</span><span class="secure">256-bit güvenli ödeme altyapısı</span></div>
          <h1>Güvenli Ödeme</h1>
          <p class="secure">Sipariş: <strong>{escape(order_id)}</strong></p>
        </div>
        <p class="status" data-status>{escape(status)}</p>
      </section>

      <section class="checkout-card">
        <div class="panel order-panel">
          <h2>Sipariş Özeti</h2>
          <div class="order-meta">
            <span>Disney | Dash</span>
            <span>{len(order["items"])} ürün</span>
          </div>
          <ul class="item-list">{rows}</ul>
          <form class="discount-form" data-discount-form>
            <label for="discount-code">İndirim kodu</label>
            <div class="discount-control">
              <input id="discount-code" name="code" value="{escape(discount_code)}" placeholder="BURCU20" autocomplete="off">
              <button type="submit">Uygula</button>
            </div>
            <p class="discount-message" data-discount-message>{discount_message}</p>
          </form>
        </div>

        <aside class="panel payment-panel">
          <h2>Ödeme</h2>
          <p class="payment-note"><strong>iyzico</strong> ile ödeme adımına geçmeden önce sipariş tutarını kontrol edin. Kampanya kodunuz varsa burada uygulayabilirsiniz.</p>
          <div class="summary-list">
            <div class="summary-row"><span>Ara toplam</span><b data-summary-subtotal>{format_order_money(summary['subtotal'])}</b></div>
            <div class="summary-row discount {discount_row_class}" data-discount-row><span data-discount-label>{discount_label}</span><b data-summary-discount>-{format_order_money(discount_amount)}</b></div>
            <div class="summary-row"><span>Kargo</span><b data-summary-shipping>{format_order_money(summary['shipping'])}</b></div>
            <div class="summary-row"><span>Vergi</span><b data-summary-tax>{format_order_money(summary['tax'])}</b></div>
            <div class="summary-row total"><span>Toplam</span><strong data-summary-total>{format_order_money(summary['total'])}</strong></div>
          </div>
          <button type="button" {disabled} data-pay>Ödemeyi tamamla</button>
          <ul class="trust-list">
            <li>iyzico güvencesiyle ödeme deneyimi</li>
            <li>BURCU20 koduyla %20 indirim</li>
            <li>Sipariş sonrası sepet otomatik temizlenir</li>
          </ul>
        </aside>
      </section>
      <a class="back-link" href="/">Mağazaya geri dön</a>
    </main>
    <script>
      const orderId = "{escape(order_id)}";
      const formatter = new Intl.NumberFormat("tr-TR", {{ style: "currency", currency: "TRY", minimumFractionDigits: 2, maximumFractionDigits: 2 }});
      const payButton = document.querySelector("[data-pay]");
      const discountForm = document.querySelector("[data-discount-form]");
      const discountInput = document.querySelector("#discount-code");
      const discountMessage = document.querySelector("[data-discount-message]");

      function money(value) {{
        return formatter.format(Number(value) || 0);
      }}

      function renderSummary(summary) {{
        document.querySelector("[data-summary-subtotal]").textContent = money(summary.subtotal);
        document.querySelector("[data-summary-shipping]").textContent = money(summary.shipping);
        document.querySelector("[data-summary-tax]").textContent = money(summary.tax);
        document.querySelector("[data-summary-total]").textContent = money(summary.total);
        const discountRow = document.querySelector("[data-discount-row]");
        const discountValue = Number(summary.discount) || 0;
        if (discountValue > 0) {{
          discountRow.classList.remove("is-hidden");
          document.querySelector("[data-discount-label]").textContent = `İndirim (${{summary.discountCode}})`;
          document.querySelector("[data-summary-discount]").textContent = `-${{money(discountValue)}}`;
        }} else {{
          discountRow.classList.add("is-hidden");
        }}
      }}

      discountForm?.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const code = discountInput.value.trim();
        if (!code) {{
          discountMessage.textContent = "İndirim kodunu girin.";
          discountMessage.classList.add("is-error");
          return;
        }}
        const button = discountForm.querySelector("button");
        button.disabled = true;
        discountMessage.classList.remove("is-error");
        discountMessage.textContent = "Kod kontrol ediliyor...";
        try {{
          const response = await fetch(`/api/orders/${{orderId}}/discount`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ code }})
          }});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "İndirim kodu uygulanamadı.");
          renderSummary(data.summary);
          discountInput.value = data.summary.discountCode || code.toUpperCase();
          discountMessage.textContent = data.message || "İndirim kodu uygulandı.";
        }} catch (error) {{
          discountMessage.textContent = error.message;
          discountMessage.classList.add("is-error");
        }} finally {{
          button.disabled = false;
        }}
      }});

      payButton?.addEventListener("click", async () => {{
        payButton.disabled = true;
        const response = await fetch("/api/orders/{escape(order_id)}/pay", {{ method: "POST" }});
        const data = await response.json();
        document.querySelector("[data-status]").textContent = data.message || "Ödeme tamamlandı.";
      }});
    </script>
  </body>
</html>"""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def serve_static(self, path: str) -> None:
        safe_path = unquote(path).lstrip("/")
        file_path = (ROOT / safe_path).resolve() if safe_path else ROOT / "index.html"
        if ROOT not in file_path.parents and file_path != ROOT / "index.html":
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            relative_parts = file_path.relative_to(ROOT).parts
        except ValueError:
            relative_parts = ()
        if any(part.startswith(".") for part in relative_parts):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw_bytes = self.rfile.read(length)
        for encoding in ("utf-8", "utf-8-sig", "cp1254", "latin-1"):
            try:
                raw = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                raw = ""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def session_id(self, query: dict) -> str:
        value = query.get("session", [""])[0] or self.headers.get("X-Dash-Session")
        return str(value or uuid.uuid4())

    def respond_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Dash-Session")

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 4173))
    host = os.environ.get("HOST", "0.0.0.0")
    load_db()
    server = ThreadingHTTPServer((host, port), DashHandler)
    print(f"Dash backend running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
