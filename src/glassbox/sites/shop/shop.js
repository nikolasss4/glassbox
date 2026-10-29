// Catalog and cart logic for Brightside Shop. Prices are in cents.
const PRODUCTS = [
  { id: "mug-blue", name: "Blue Ceramic Mug", category: "Kitchen", price: 1400, rating: 4.6 },
  { id: "mug-white", name: "White Ceramic Mug", category: "Kitchen", price: 1200, rating: 4.2 },
  { id: "kettle", name: "Gooseneck Kettle", category: "Kitchen", price: 5900, rating: 4.7 },
  { id: "hp-studio", name: "Studio Headphones", category: "Audio", price: 12900, rating: 4.8 },
  { id: "hp-budget", name: "Everyday Headphones", category: "Audio", price: 3900, rating: 4.0 },
  { id: "hp-sport", name: "Sport Earbuds Headphones", category: "Audio", price: 4900, rating: 4.1 },
  { id: "speaker", name: "Pocket Speaker", category: "Audio", price: 2900, rating: 3.9 },
  { id: "lamp-arc", name: "Arc Floor Lamp", category: "Home", price: 8900, rating: 4.4 },
  { id: "lamp-desk", name: "Mini Desk Lamp", category: "Home", price: 2450, rating: 4.3 },
  { id: "lamp-clip", name: "Clip-on Reading Lamp", category: "Home", price: 3150, rating: 4.1 },
  { id: "plant", name: "Desk Plant", category: "Home", price: 1800, rating: 4.5 },
  { id: "tote", name: "Linen Tote Bag", category: "Accessories", price: 2200, rating: 4.4 },
  { id: "mouse", name: "Wireless Mouse", category: "Office", price: 2600, rating: 4.2 },
  { id: "keyboard", name: "Mechanical Keyboard", category: "Office", price: 8400, rating: 4.7 },
  { id: "notebook", name: "Dot Grid Notebook", category: "Office", price: 900, rating: 4.6 },
  { id: "book-ml", name: "Practical Machine Learning", category: "Books", price: 3900, rating: 4.5 },
  { id: "book-web", name: "The Web, Explained", category: "Books", price: 2900, rating: 4.8 },
  { id: "book-sql", name: "SQL for Busy People", category: "Books", price: 2500, rating: 4.7 },
  { id: "book-ux", name: "Designing Calm Interfaces", category: "Books", price: 3300, rating: 4.3 },
];
const COUPONS = { GLASS10: 0.1 };
const money = (c) => "$" + (c / 100).toFixed(2);
const product = (id) => PRODUCTS.find((p) => p.id === id);
const cart = () => gbStore.get("shop:cart", []);
const saveCart = (c) => { gbStore.set("shop:cart", c.filter((l) => l.qty > 0)); renderCartBadge(); };
function addToCart(id, qty) {
  const c = cart();
  const line = c.find((l) => l.id === id);
  if (line) line.qty += qty; else c.push({ id, qty });
  saveCart(c);
}
function cartTotals() {
  const subtotal = cart().reduce((s, l) => s + product(l.id).price * l.qty, 0);
  const code = gbStore.get("shop:coupon", null);
  const discount = code ? Math.round(subtotal * COUPONS[code]) : 0;
  return { subtotal, discount, total: subtotal - discount, code };
}
function renderCartBadge() {
  const el = document.getElementById("cart-count");
  if (el) el.textContent = cart().reduce((s, l) => s + l.qty, 0);
}
function shopHeader() {
  document.body.insertAdjacentHTML("afterbegin", `
    <div style="background:#ffd166;padding:6px 24px;font-size:14px">Autumn sale: use code <strong>GLASS10</strong> for 10% off your order.</div>
    <header class="site"><a class="brand" href="/sites/shop/">Brightside</a>
      <nav><a href="/sites/shop/">Shop</a><a href="/sites/shop/cart.html">Cart (<span id="cart-count">0</span>)</a></nav></header>`);
  renderCartBadge();
}
