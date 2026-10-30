/* Flask JSON API와 통신하는 순수 브라우저 JavaScript입니다. */
const root = document.querySelector("#app");
const nav = document.querySelector("#site-nav");
const menuToggle = document.querySelector("#menu-toggle");
const logoutButton = document.querySelector("#logout-button");
const guestLink = document.querySelector("[data-guest-link]");
const toast = document.querySelector("#toast");

let signedInUser = null;
let toastTimer = null;

class ApiError extends Error {
  constructor(message, statusCode, body) {
    super(message);
    this.statusCode = statusCode;
    this.body = body;
  }
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const message = body?.detail || body?.message || "요청을 처리하지 못했습니다.";
    throw new ApiError(typeof message === "string" ? message : "입력값을 확인해 주세요.", response.status, body);
  }
  return body;
}

function requestOptions(method, body) {
  return { method, body: JSON.stringify(body) };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function won(value) {
  const amount = typeof value === "bigint" ? value : BigInt(Math.trunc(Number(value) || 0));
  return `${amount.toLocaleString("ko-KR")}원`;
}

function dateText(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : new Intl.DateTimeFormat("ko-KR", {
    year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function productEmoji(name) {
  const text = String(name || "");
  if (/가방|백팩|파우치/.test(text)) return "👜";
  if (/신발|운동화/.test(text)) return "👟";
  if (/티|옷|셔츠|의류/.test(text)) return "👕";
  if (/책|문구/.test(text)) return "📚";
  return "🛍️";
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function updateNavigation() {
  guestLink.hidden = Boolean(signedInUser);
  document.querySelector("[data-admin-link]").hidden = signedInUser?.role !== "admin";
  logoutButton.hidden = !signedInUser;
  logoutButton.textContent = signedInUser ? `${signedInUser.name} · 로그아웃` : "로그아웃";
}

async function refreshUser() {
  try {
    signedInUser = await api("/api/members/me");
  } catch {
    signedInUser = null;
  }
  updateNavigation();
}

function routeInfo() {
  const hash = window.location.hash.slice(1) || "/products";
  const separator = hash.indexOf("?");
  const pathname = separator < 0 ? hash : hash.slice(0, separator);
  const query = new URLSearchParams(separator < 0 ? "" : hash.slice(separator + 1));
  return { pathname, query };
}

function pageHeader(eyebrow, title, copy = "") {
  return `<div class="section-heading"><div><p class="eyebrow">${escapeHtml(eyebrow)}</p><h1 class="page-title">${escapeHtml(title)}</h1>${copy ? `<p class="page-copy">${escapeHtml(copy)}</p>` : ""}</div></div>`;
}

function errorPanel(message, back = "#/products") {
  return `<section class="form-card centered"><div class="result-mark">!</div><h1 class="page-title">화면을 불러오지 못했어요</h1><p class="page-copy">${escapeHtml(message)}</p><div class="button-row" style="justify-content:center;margin-top:22px"><a class="button button-secondary" href="${back}">돌아가기</a><a class="button" href="#/login">로그인</a></div></section>`;
}

function showFormError(id, message) {
  const element = document.getElementById(id);
  if (element) element.textContent = message;
}

function productCard(product) {
  const soldOut = product.stock < 1;
  return `<article class="product-card">
    <a href="#/products/${encodeURIComponent(product.id)}" aria-label="${escapeHtml(product.name)} 상세 보기">
      <div class="product-visual" aria-hidden="true"><span class="product-emoji">${productEmoji(product.name)}</span></div>
    </a>
    <div class="product-body">
      <a href="#/products/${encodeURIComponent(product.id)}"><h2 class="product-name">${escapeHtml(product.name)}</h2></a>
      <p class="product-description">${escapeHtml(product.description || "상품 설명이 준비 중입니다.")}</p>
      <div class="product-meta"><div><div class="price">${won(product.price)}</div><div class="stock ${soldOut ? "stock-out" : ""}">${soldOut ? "품절" : `재고 ${Number(product.stock).toLocaleString("ko-KR")}개`}</div></div>
        <a class="button button-small ${soldOut ? "button-secondary" : ""}" href="#/products/${encodeURIComponent(product.id)}">${soldOut ? "상세 보기" : "상품 보기"}</a>
      </div>
    </div>
  </article>`;
}

async function renderProducts() {
  const result = await api("/api/products?limit=100&offset=0");
  root.innerHTML = `<section class="hero">
    <div class="hero-content"><p class="eyebrow">매일의 좋은 선택</p><h1>필요한 물건을<br>편하게 만나보세요.</h1><p>마음에 드는 상품을 살펴보고 장바구니에 담아 주문해 보세요.</p><button id="scroll-products" class="button" type="button">상품 둘러보기 <span aria-hidden="true">↓</span></button></div>
    <div class="hero-art" aria-hidden="true"><div class="hero-orb">moa</div></div>
  </section>
  <section id="products-list" class="product-section">
    <div class="section-heading"><div><p class="eyebrow">SHOP ALL</p><h2 class="page-title">상품 둘러보기</h2></div><span class="small-note">총 ${Number(result.total).toLocaleString("ko-KR")}개</span></div>
    ${result.items.length ? `<div class="product-grid">${result.items.map(productCard).join("")}</div>` : `<div class="panel empty-state">등록된 상품이 없습니다.</div>`}
  </section>`;
  root.querySelector("#scroll-products")?.addEventListener("click", () => {
    root.querySelector("#products-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

async function renderProductDetail(productId) {
  const product = await api(`/api/products/${encodeURIComponent(productId)}`);
  const soldOut = product.stock < 1;
  root.innerHTML = `<div class="small-note"><a href="#/products">← 상품 목록</a></div>
    <section class="detail-layout" style="margin-top:20px">
      <div class="detail-visual" aria-hidden="true"><span class="product-emoji">${productEmoji(product.name)}</span></div>
      <div class="detail-info"><p class="eyebrow">PRODUCT DETAIL</p><h1 class="page-title">${escapeHtml(product.name)}</h1>
        <p class="detail-description">${escapeHtml(product.description || "상품 설명이 준비 중입니다.")}</p>
        <p class="detail-price">${won(product.price)}</p><p class="stock ${soldOut ? "stock-out" : ""}">${soldOut ? "현재 품절된 상품입니다." : `남은 수량 ${Number(product.stock).toLocaleString("ko-KR")}개`}</p>
        <div class="quantity-control" style="margin-top:18px"><button type="button" data-quantity="minus" aria-label="수량 감소">−</button><input id="detail-quantity" type="number" min="1" max="${Math.max(1, product.stock)}" value="1" inputmode="numeric" aria-label="구매 수량"><button type="button" data-quantity="plus" aria-label="수량 증가">+</button></div>
        <div class="detail-actions"><button id="add-to-cart" class="button button-secondary" type="button" ${soldOut ? "disabled" : ""}>장바구니 담기</button><button id="buy-now" class="button" type="button" ${soldOut ? "disabled" : ""}>바로 주문</button></div>
      </div>
    </section>`;
  root.querySelectorAll("[data-quantity]").forEach((button) => button.addEventListener("click", () => {
    const input = document.querySelector("#detail-quantity");
    const max = Math.max(1, Number(product.stock));
    const next = Number(input.value || 1) + (button.dataset.quantity === "plus" ? 1 : -1);
    input.value = String(Math.min(max, Math.max(1, next)));
  }));
  root.querySelector("#add-to-cart")?.addEventListener("click", async () => {
    try {
      const quantity = Number(document.querySelector("#detail-quantity").value);
      await api("/api/cart/items", requestOptions("POST", { product_id: product.id, quantity }));
      showToast("장바구니에 담았습니다.");
    } catch (error) { showToast(error.message); }
  });
  root.querySelector("#buy-now")?.addEventListener("click", () => {
    const quantity = Number(document.querySelector("#detail-quantity").value);
    window.location.hash = `#/checkout?source=buy_now&product_id=${encodeURIComponent(product.id)}&quantity=${encodeURIComponent(quantity)}`;
  });
}

function cartItem(item) {
  return `<article class="cart-item">
    <div><h3 class="cart-item-name">${escapeHtml(item.product_name)}</h3><div class="cart-item-price">${won(item.unit_price)} · 재고 ${Number(item.stock).toLocaleString("ko-KR")}개</div><div class="small-note" style="margin-top:6px">합계 ${won(item.line_amount)}</div></div>
    <div class="cart-item-controls"><label class="small-note" for="qty-${escapeHtml(item.product_id)}">수량</label><input id="qty-${escapeHtml(item.product_id)}" type="number" min="1" max="${Math.max(1, item.stock)}" value="${Number(item.quantity)}" data-cart-quantity="${escapeHtml(item.product_id)}" aria-label="${escapeHtml(item.product_name)} 수량"><button class="remove-button" type="button" data-remove-product="${escapeHtml(item.product_id)}">삭제</button></div>
  </article>`;
}

async function renderCart() {
  const cart = await api("/api/cart");
  root.innerHTML = `${pageHeader("YOUR BAG", "장바구니", "주문할 상품과 수량을 확인해 주세요.")}
    ${cart.items.length ? `<div class="content-grid"><section class="panel panel-pad"><div class="cart-list">${cart.items.map(cartItem).join("")}</div></section>
      <aside class="panel panel-pad summary-panel"><h2 class="panel-title">주문 요약</h2><div class="summary-row"><span>상품 수</span><strong>${cart.items.length}개</strong></div><div class="summary-row summary-total"><span>총 상품 금액</span><strong>${won(cart.total_amount)}</strong></div><p class="field-hint">배송비는 결제 금액에 포함되지 않는 MVP 예시입니다.</p><a class="button button-block" href="#/checkout?source=cart" style="margin-top:14px">주문서 작성</a></aside></div>`
      : `<section class="panel empty-state"><div class="result-mark">＋</div><h2>장바구니가 비어 있어요</h2><p>마음에 드는 상품을 담아보세요.</p><a class="button" href="#/products">상품 둘러보기</a></section>`}`;
  root.querySelectorAll("[data-cart-quantity]").forEach((input) => input.addEventListener("change", async () => {
    const quantity = Number(input.value);
    try {
      await api(`/api/cart/items/${encodeURIComponent(input.dataset.cartQuantity)}`, requestOptions("PATCH", { quantity }));
      showToast("수량을 변경했습니다.");
      await renderCart();
    } catch (error) { showToast(error.message); await renderCart(); }
  }));
  root.querySelectorAll("[data-remove-product]").forEach((button) => button.addEventListener("click", async () => {
    try {
      await api(`/api/cart/items/${encodeURIComponent(button.dataset.removeProduct)}`, { method: "DELETE" });
      showToast("상품을 장바구니에서 삭제했습니다.");
      await renderCart();
    } catch (error) { showToast(error.message); }
  }));
}

function shippingFields(profile = {}) {
  return `<div class="form-grid">
    <div class="field"><label for="recipient-name">받는 분</label><input id="recipient-name" name="recipient_name" required maxlength="100" value="${escapeHtml(profile.name || "")}" autocomplete="name"></div>
    <div class="field"><label for="recipient-phone">연락처</label><input id="recipient-phone" name="recipient_phone" required maxlength="30" value="${escapeHtml(profile.phone || "")}" autocomplete="tel" placeholder="010-1234-5678"></div>
    <div class="field field-full"><label for="shipping-address">배송 주소</label><textarea id="shipping-address" name="shipping_address" required maxlength="500" autocomplete="street-address">${escapeHtml(profile.address || "")}</textarea></div>
  </div>`;
}

async function renderCheckout(query) {
  const source = query.get("source") === "buy_now" ? "buy_now" : "cart";
  let cart = null;
  let product = null;
  const requestedQuantity = Number(query.get("quantity") || 1);
  let quantity = Number.isSafeInteger(requestedQuantity) && requestedQuantity > 0 ? requestedQuantity : 1;
  let total = 0;
  if (source === "cart") {
    cart = await api("/api/cart");
    total = cart.total_amount;
  } else {
    const productId = query.get("product_id");
    if (!productId) throw new Error("주문할 상품을 찾을 수 없습니다.");
    product = await api(`/api/products/${encodeURIComponent(productId)}`);
    total = BigInt(product.price) * BigInt(quantity);
  }
  const profile = signedInUser || {};
  const review = cart
    ? cart.items.map((item) => `<div class="summary-row"><span>${escapeHtml(item.product_name)} × ${Number(item.quantity)}</span><strong>${won(item.line_amount)}</strong></div>`).join("")
    : `<div class="summary-row"><span>${escapeHtml(product.name)} × ${quantity}</span><strong>${won(total)}</strong></div>`;
  root.innerHTML = `<div class="form-card form-card-wide"><div class="checkout-progress"><span class="progress-step active"></span><span class="progress-step"></span></div>
    <div class="form-header"><p class="eyebrow">CHECKOUT · 01</p><h1 class="page-title">배송 정보를 입력해 주세요</h1><p class="page-copy">주문이 생성된 뒤 모의 결제 화면으로 이동합니다.</p></div>
    <form id="checkout-form">${shippingFields(profile)}<div id="checkout-error" class="form-error" role="alert"></div>
      <section class="panel panel-pad" style="margin:7px 0 20px"><h2 class="panel-title">주문 상품</h2>${review}<div class="summary-row summary-total"><span>결제 예정 금액</span><strong>${won(total)}</strong></div></section>
      <button class="button button-block" type="submit" ${source === "cart" && !cart.items.length ? "disabled" : ""}>주문 생성 후 결제하기</button>
    </form></div>`;
  root.querySelector("#checkout-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const shipping = {
      recipient_name: form.get("recipient_name"),
      recipient_phone: form.get("recipient_phone"),
      shipping_address: form.get("shipping_address"),
    };
    const orderBody = source === "cart"
      ? { source: "cart", ...shipping }
      : { source: "buy_now", product_id: product.id, quantity, ...shipping };
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const order = await api("/api/orders", requestOptions("POST", orderBody));
      window.location.hash = `#/payment?order_id=${encodeURIComponent(order.id)}`;
    } catch (error) {
      showFormError("checkout-error", error.message);
      button.disabled = false;
    }
  });
}

async function renderPayment(query) {
  const orderId = query.get("order_id");
  if (!orderId) throw new Error("주문 번호가 없습니다.");
  const order = await api(`/api/orders/${encodeURIComponent(orderId)}`);
  root.innerHTML = `<div class="form-card form-card-wide"><div class="checkout-progress"><span class="progress-step active"></span><span class="progress-step active"></span></div>
    <div class="form-header"><p class="eyebrow">CHECKOUT · 02</p><h1 class="page-title">모의 결제</h1><p class="page-copy">실제 결제는 발생하지 않습니다. 테스트할 결과를 선택해 주세요.</p></div>
    <section class="panel panel-pad"><div class="summary-row"><span>주문 번호</span><strong>${escapeHtml(order.id.slice(0, 8))}…</strong></div>
      ${order.items.map((item) => `<div class="summary-row"><span>${escapeHtml(item.product_name)} × ${Number(item.quantity)}</span><strong>${won(item.line_amount)}</strong></div>`).join("")}
      <div class="summary-row summary-total"><span>결제 금액</span><strong>${won(order.total_amount)}</strong></div></section>
    <div id="payment-result" style="margin-top:18px"></div>
    ${order.status === "paid" ? `<div class="panel panel-pad centered" style="margin-top:16px"><span class="badge badge-paid">결제 완료</span><p class="page-copy">이 주문은 이미 결제가 완료되었습니다.</p><a class="button" href="#/orders" style="margin-top:12px">구매내역 보기</a></div>` : `<div class="payment-choice"><button type="button" data-pay-success="true"><strong>결제 성공으로 처리</strong><span>재고를 확인하고 결제 완료 상태로 저장합니다.</span></button><button type="button" data-pay-success="false"><strong>결제 실패로 처리</strong><span>실패 내역을 저장하고 주문은 대기 상태로 둡니다.</span></button></div>`}
    <div class="centered"><a class="text-button" href="#/products">상품 목록으로</a></div></div>`;
  root.querySelectorAll("[data-pay-success]").forEach((button) => button.addEventListener("click", async () => {
    const controls = root.querySelectorAll("[data-pay-success]");
    controls.forEach((control) => { control.disabled = true; });
    const result = document.querySelector("#payment-result");
    try {
      const payment = await api(`/api/orders/${encodeURIComponent(order.id)}/payments`, requestOptions("POST", {
        simulate_success: button.dataset.paySuccess === "true",
      }));
      showPaymentResult(result, payment);
      if (payment.payment.status === "failed") controls.forEach((control) => { control.disabled = false; });
    } catch (error) {
      if (error.body?.payment) showPaymentResult(result, error.body);
      else result.innerHTML = `<p class="form-error" role="alert">${escapeHtml(error.message)}</p>`;
      controls.forEach((control) => { control.disabled = false; });
    }
  }));
}

function showPaymentResult(container, result) {
  const successful = result.payment.status === "success";
  container.innerHTML = `<section class="panel panel-pad centered"><div class="result-mark ${successful ? "" : "badge-failed"}">${successful ? "✓" : "!"}</div>
    <span class="badge ${successful ? "badge-paid" : "badge-failed"}">${successful ? "결제 성공" : "결제 실패"}</span>
    <p class="page-copy">${escapeHtml(result.payment.failure_reason || (result.already_paid ? "이미 결제된 주문입니다." : "결제 결과를 저장했습니다."))}</p>
    <div class="summary-row summary-total"><span>결제 금액</span><strong>${won(result.payment.amount)}</strong></div>
    <div class="button-row" style="justify-content:center"><a class="button" href="#/orders">구매내역 보기</a><a class="button button-secondary" href="#/products">상품 계속 보기</a></div>
  </section>`;
}

function orderCard(order) {
  const paid = order.status === "paid";
  return `<article class="order-card"><div class="order-top"><div><p class="order-date">${dateText(order.ordered_at)}</p><p class="order-id">주문번호 ${escapeHtml(order.id)}</p></div><span class="badge ${paid ? "badge-paid" : "badge-pending"}">${paid ? "결제 완료" : "결제 대기"}</span></div>
    <div class="order-items">${order.items.map((item) => `<div>${escapeHtml(item.product_name)} · ${Number(item.quantity)}개 · ${won(item.unit_price)}</div>`).join("")}</div>
    <div class="order-bottom"><span class="small-note">받는 분 ${escapeHtml(order.recipient_name)}</span><strong class="order-total">${won(order.total_amount)}</strong></div>
    ${paid ? "" : `<a class="button button-secondary button-small" style="margin-top:15px" href="#/payment?order_id=${encodeURIComponent(order.id)}">결제 이어하기</a>`}
  </article>`;
}

async function renderOrders() {
  const orders = await api("/api/members/me/orders");
  root.innerHTML = `${pageHeader("ORDER HISTORY", "구매내역", "주문 상태와 상품 정보를 확인할 수 있습니다.")}
    ${orders.length ? `<div class="order-list">${orders.map(orderCard).join("")}</div>` : `<section class="panel empty-state"><div class="result-mark">◎</div><h2>아직 주문 내역이 없습니다</h2><p>마음에 드는 상품을 찾아보세요.</p><a class="button" href="#/products">상품 둘러보기</a></section>`}`;
}

async function renderAccount() {
  const profile = await api("/api/members/me");
  signedInUser = profile;
  updateNavigation();
  root.innerHTML = `<div class="form-card form-card-wide"><div class="form-header"><p class="eyebrow">MY ACCOUNT</p><h1 class="page-title">회원정보</h1><p class="page-copy">계정 정보와 배송에 사용할 기본 정보를 관리합니다.</p></div>
    <form id="profile-form"><div class="field"><label for="account-email">이메일</label><input id="account-email" type="email" value="${escapeHtml(profile.email)}" disabled></div>
      <div class="field"><label for="account-name">이름</label><input id="account-name" name="name" required maxlength="100" value="${escapeHtml(profile.name)}"></div>
      <div class="field"><label for="account-phone">연락처</label><input id="account-phone" name="phone" maxlength="30" value="${escapeHtml(profile.phone || "")}" placeholder="010-1234-5678"></div>
      <div class="field"><label for="account-address">주소</label><textarea id="account-address" name="address" maxlength="500">${escapeHtml(profile.address || "")}</textarea></div>
      <div id="profile-error" class="form-error" role="alert"></div><button class="button" type="submit">회원정보 저장</button>
    </form>
    <div class="divider"></div><form id="password-form"><h2 class="panel-title">비밀번호 변경</h2>
      <div class="field"><label for="current-password">현재 비밀번호</label><input id="current-password" name="current_password" type="password" required maxlength="128" autocomplete="current-password"></div>
      <div class="field"><label for="new-password">새 비밀번호</label><input id="new-password" name="new_password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"><span class="field-hint">8자 이상 입력해 주세요.</span></div>
      <div id="password-error" class="form-error" role="alert"></div><button class="button button-secondary" type="submit">비밀번호 변경</button>
    </form>
    <section class="danger-zone"><h3>회원 탈퇴</h3><p>탈퇴하면 로그인할 수 없습니다. 기존 주문 및 결제 내역은 보존됩니다.</p><button id="delete-account" class="button button-danger button-small" type="button">회원 탈퇴</button></section>
  </div>`;
  root.querySelector("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const updated = await api("/api/members/me", requestOptions("PATCH", {
        name: data.get("name"),
        phone: data.get("phone") || null,
        address: data.get("address") || null,
      }));
      signedInUser = updated;
      updateNavigation();
      showToast("회원정보를 저장했습니다.");
    } catch (error) { showFormError("profile-error", error.message); }
  });
  root.querySelector("#password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await api("/api/members/me/password", requestOptions("PUT", {
        current_password: data.get("current_password"), new_password: data.get("new_password"),
      }));
      root.querySelector("#password-form").reset();
      showFormError("password-error", "");
      signedInUser = null;
      updateNavigation();
      showToast("비밀번호를 변경했습니다. 다시 로그인해 주세요.");
      window.location.hash = "#/login";
    } catch (error) { showFormError("password-error", error.message); }
  });
  root.querySelector("#delete-account").addEventListener("click", async () => {
    if (!window.confirm("회원 탈퇴를 진행할까요? 기존 주문내역은 보존됩니다.")) return;
    try {
      await api("/api/members/me", { method: "DELETE" });
      signedInUser = null;
      updateNavigation();
      showToast("회원 탈퇴가 완료되었습니다.");
      window.location.hash = "#/products";
    } catch (error) { showToast(error.message); }
  });
}

function renderLogin() {
  root.innerHTML = `<section class="form-card"><div class="form-header"><p class="eyebrow">WELCOME BACK</p><h1 class="page-title">로그인</h1><p class="page-copy">로그인하고 편리하게 주문을 관리하세요.</p></div>
    <form id="login-form"><div class="field"><label for="login-email">이메일</label><input id="login-email" name="email" type="email" required maxlength="254" autocomplete="email"></div>
      <div class="field"><label for="login-password">비밀번호</label><input id="login-password" name="password" type="password" required maxlength="128" autocomplete="current-password"></div>
      <div id="login-error" class="form-error" role="alert"></div><button class="button button-block" type="submit">로그인</button>
    </form><p class="form-switch">아직 회원이 아니신가요? <a href="#/signup">회원가입</a></p></section>`;
  root.querySelector("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const result = await api("/api/auth/login", requestOptions("POST", {
        email: data.get("email"), password: data.get("password"),
      }));
      signedInUser = result.user;
      updateNavigation();
      showToast("로그인되었습니다.");
      window.location.hash = "#/products";
    } catch (error) {
      showFormError("login-error", error.message);
      button.disabled = false;
    }
  });
}

function renderSignup() {
  root.innerHTML = `<section class="form-card"><div class="form-header"><p class="eyebrow">JOIN MOA</p><h1 class="page-title">회원가입</h1><p class="page-copy">간단한 정보를 입력해 계정을 만들어 주세요.</p></div>
    <form id="signup-form"><div class="field"><label for="signup-name">이름</label><input id="signup-name" name="name" required maxlength="100" autocomplete="name"></div>
      <div class="field"><label for="signup-email">이메일</label><input id="signup-email" name="email" type="email" required maxlength="254" autocomplete="email"></div>
      <div class="field"><label for="signup-phone">연락처 <span class="small-note">선택</span></label><input id="signup-phone" name="phone" maxlength="30" autocomplete="tel" placeholder="010-1234-5678"></div>
      <div class="field"><label for="signup-address">주소 <span class="small-note">선택</span></label><textarea id="signup-address" name="address" maxlength="500" autocomplete="street-address"></textarea></div>
      <div class="field"><label for="signup-password">비밀번호</label><input id="signup-password" name="password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"><span class="field-hint">8자 이상 입력해 주세요.</span></div>
      <div id="signup-error" class="form-error" role="alert"></div><button class="button button-block" type="submit">가입하기</button>
    </form><p class="form-switch">이미 계정이 있으신가요? <a href="#/login">로그인</a></p></section>`;
  root.querySelector("#signup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const button = event.currentTarget.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const result = await api("/api/auth/signup", requestOptions("POST", {
        name: data.get("name"), email: data.get("email"), password: data.get("password"),
        phone: data.get("phone") || null, address: data.get("address") || null,
      }));
      showToast(result.message);
      window.location.hash = "#/login";
    } catch (error) {
      showFormError("signup-error", error.message);
      button.disabled = false;
    }
  });
}

async function renderAdmin() {
  // The orders request enforces the server's current role before rendering controls.
  const orders = await api('/api/admin/orders?limit=100');
  const products = await api('/api/products?limit=100');
  root.innerHTML = `${pageHeader('ADMIN', '상품·주문 관리', '상품 가격과 재고를 관리하고 고객 주문을 확인하세요.')}
    <section class="form-card"><h2 class="panel-title">상품 등록 / 수정</h2>
    <form id="admin-product-form">
      <div class="field"><label for="admin-product">수정할 상품</label><select id="admin-product"><option value="">새 상품 등록</option>${products.items.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join('')}</select></div>
      <div class="field"><label for="admin-name">상품명</label><input id="admin-name" name="name" maxlength="200" required></div>
      <div class="field"><label for="admin-description">설명</label><textarea id="admin-description" name="description" maxlength="5000"></textarea></div>
      <div class="field"><label for="admin-price">가격 (원)</label><input id="admin-price" name="price" type="number" min="1" max="999999999999" step="1" required></div>
      <div class="field"><label for="admin-stock">재고</label><input id="admin-stock" name="stock" type="number" min="0" max="2147483647" step="1" required></div>
      <p id="admin-error" class="form-error" role="alert"></p><button class="button" type="submit">저장</button>
    </form></section>
    <section class="panel" style="margin-top:24px"><h2 class="panel-title">최근 주문 (최대 100건)</h2>
    ${orders.length ? orders.map(order => `<article class="cart-item"><div><h3>${escapeHtml(order.recipient_name)} · ${escapeHtml(order.status)}</h3><p>${escapeHtml(order.id)}</p><p>${escapeHtml(order.recipient_phone)} · ${escapeHtml(order.shipping_address)}</p><p>${order.items.map(i => `${escapeHtml(i.product_name)} × ${Number(i.quantity)}`).join(', ')}</p></div><strong>${won(order.total_amount)}</strong></article>`).join('') : '<p>주문이 없습니다.</p>'}</section>`;
  const form = root.querySelector('#admin-product-form');
  const select = root.querySelector('#admin-product');
  select.addEventListener('change', () => {
    const product = products.items.find(p => p.id === select.value);
    for (const key of ['name', 'description', 'price', 'stock']) form.elements[key].value = product?.[key] ?? '';
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const id = select.value;
      await api(`/api/admin/products${id ? '/' + encodeURIComponent(id) : ''}`, requestOptions(id ? 'PUT' : 'POST', {
        name: data.get('name'), description: data.get('description'), price: Number(data.get('price')), stock: Number(data.get('stock')),
      }));
      showToast('상품을 저장했습니다.');
      await renderAdmin();
    } catch (error) { showFormError('admin-error', error.message); }
    finally { button.disabled = false; }
  });
}

function renderProtectedError(error) {
  if (error.statusCode === 401) {
    root.innerHTML = `<section class="form-card centered"><div class="result-mark">↗</div><p class="eyebrow">SIGN IN REQUIRED</p><h1 class="page-title">로그인이 필요합니다</h1><p class="page-copy">이 화면을 이용하려면 먼저 로그인해 주세요.</p><a class="button" href="#/login" style="margin-top:20px">로그인 화면으로</a></section>`;
    return;
  }
  root.innerHTML = errorPanel(error.message);
}

async function renderRoute() {
  const { pathname, query } = routeInfo();
  nav.classList.remove("open");
  menuToggle.setAttribute("aria-expanded", "false");
  root.innerHTML = `<div class="loading-state">화면을 불러오고 있습니다…</div>`;
  try {
    if (pathname === "/products") await renderProducts();
    else if (/^\/products\/[^/]+$/.test(pathname)) await renderProductDetail(decodeURIComponent(pathname.split("/")[2]));
    else if (pathname === "/login") renderLogin();
    else if (pathname === "/signup") renderSignup();
    else if (pathname === "/cart") await renderCart();
    else if (pathname === "/checkout") await renderCheckout(query);
    else if (pathname === "/payment") await renderPayment(query);
    else if (pathname === "/account") await renderAccount();
    else if (pathname === "/orders") await renderOrders();
    else if (pathname === "/admin") await renderAdmin();
    else root.innerHTML = errorPanel("요청한 화면을 찾을 수 없습니다.");
    root.focus({ preventScroll: true });
  } catch (error) {
    renderProtectedError(error);
  }
}

menuToggle.addEventListener("click", () => {
  const isOpen = nav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "메뉴 닫기" : "메뉴 열기");
});

nav.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    nav.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", "false");
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
    signedInUser = null;
    updateNavigation();
    showToast("로그아웃되었습니다.");
    window.location.hash = "#/products";
  } catch (error) { showToast(error.message); }
});

window.addEventListener("hashchange", renderRoute);
// Email confirmation establishes the email identity; login still goes through the server.
// Remove Supabase's implicit-flow fragments without persisting tokens in the browser.
if (/^#(?:access_token|error)=/.test(window.location.hash)) {
  const failed = window.location.hash.startsWith("#error=");
  window.history.replaceState(null, "", window.location.pathname + (failed ? "#/login" : "#/products"));
  showToast(failed ? "이메일 인증 링크를 확인해 주세요." : "이메일 인증을 확인했습니다. 로그인 후 서비스를 이용할 수 있습니다.");
}
refreshUser().finally(renderRoute);
