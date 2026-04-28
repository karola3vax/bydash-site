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


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / ".data")).expanduser()
DB_PATH = DATA_DIR / "store.json"
DB_LOCK = Lock()

PRODUCT_PRICE = 34.99

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


def cart_payload(items: list[dict]) -> dict:
    subtotal = money(sum(item["price"] * item["quantity"] for item in items))
    shipping = 0 if subtotal >= 50 or subtotal == 0 else 6.95
    tax = money(subtotal * 0.08)
    total = money(subtotal + shipping + tax)
    return {
        "items": items,
        "summary": {
            "currency": "USD",
            "subtotal": subtotal,
            "shipping": money(shipping),
            "tax": tax,
            "total": total,
            "freeShippingThreshold": 50,
        },
    }


def session_cart(db: dict, session_id: str) -> list[dict]:
    session = db["sessions"].setdefault(session_id, {"cart": []})
    return session.setdefault("cart", [])


def make_cart_item(variant: dict, quantity: int) -> dict:
    return {
        "key": variant["key"],
        "id": variant["id"],
        "name": variant["name"],
        "sku": variant["sku"],
        "image": variant["image"],
        "price": PRODUCT_PRICE,
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
            self.respond_json({
                "price": PRODUCT_PRICE,
                "variants": VARIANTS,
                "searchItems": SEARCH_ITEMS,
            })
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
        rows = "\n".join(
            f"<li><span>{escape(item['name'])} x {item['quantity']}</span><strong>${item['price'] * item['quantity']:.2f}</strong></li>"
            for item in order["items"]
        )
        summary = order["summary"]
        status = "Ödeme tamamlandı" if order["status"] == "paid" else "Ödeme bekleniyor"
        disabled = "disabled" if order["status"] == "paid" else ""
        page = f"""<!doctype html>
<html lang="tr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>iyzico Ödeme - {escape(order_id)}</title>
    <style>
      body {{ margin:0; font-family: Arial, sans-serif; color:#003847; background:#f6fbfd; }}
      main {{ width:min(720px, calc(100% - 32px)); margin:48px auto; background:#fff; border:1px solid #d7e5ea; padding:32px; }}
      h1 {{ margin:0 0 8px; font-size:28px; }}
      .badge {{ display:inline-block; background:#13a4d8; color:#fff; border-radius:16px; padding:4px 10px; font-weight:700; }}
      ul {{ padding:0; list-style:none; border-top:1px solid #d7e5ea; margin:24px 0; }}
      li {{ display:flex; justify-content:space-between; gap:16px; padding:14px 0; border-bottom:1px solid #d7e5ea; }}
      dl {{ display:grid; grid-template-columns:1fr auto; gap:10px 18px; }}
      dt, dd {{ margin:0; }}
      button {{ width:100%; border:0; border-radius:999px; background:#13a4d8; color:#fff; padding:16px; font-weight:700; font-size:16px; cursor:pointer; }}
      button:disabled {{ opacity:.5; cursor:default; }}
      a {{ color:#003847; }}
      .status {{ margin:20px 0; font-weight:700; }}
    </style>
  </head>
  <body>
    <main>
      <p><span class="badge">iyzico</span></p>
      <h1>Güvenli Ödeme</h1>
      <p>Sipariş: {escape(order_id)}</p>
      <p class="status" data-status>{escape(status)}</p>
      <ul>{rows}</ul>
      <dl>
        <dt>Ara toplam</dt><dd>${summary['subtotal']:.2f}</dd>
        <dt>Kargo</dt><dd>${summary['shipping']:.2f}</dd>
        <dt>Vergi</dt><dd>${summary['tax']:.2f}</dd>
        <dt><strong>Toplam</strong></dt><dd><strong>${summary['total']:.2f}</strong></dd>
      </dl>
      <button type="button" {disabled} data-pay>Ödemeyi tamamla</button>
      <p><a href="/">Mağazaya geri dön</a></p>
    </main>
    <script>
      const button = document.querySelector("[data-pay]");
      button?.addEventListener("click", async () => {{
        button.disabled = true;
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
