const API_BASE = "https://ca-reddy-autocare-api.greengrass-25a61570.eastus2.azurecontainerapps.io";
const key = "reddy_autocare_token";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem(key);
let pricingData = null;
let customerVehicles = [];

async function api(path, opt = {}) {
  const headers = { ...(opt.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opt.body) headers["Content-Type"] = "application/json";
  const response = await fetch(API_BASE + path, { ...opt, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.detail || "Request failed");
  return data;
}

function money(paise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

function showTab(tab) {
  $("login-form").classList.toggle("hidden", tab !== "login");
  $("register-form").classList.toggle("hidden", tab !== "register");
  document.querySelectorAll(".tabs button").forEach(button => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  $("login-message").textContent = "";
  $("register-message").textContent = "";
}

function openAuth(tab = "login") {
  $("auth-modal").classList.remove("hidden");
  showTab(tab);
}

function closeAuth() {
  $("auth-modal").classList.add("hidden");
}

function bookOrLogin() {
  if (token) $("app-view").scrollIntoView();
  else openAuth("register");
}

$("open-login").onclick = () => openAuth("login");
["hero-book", "doorstep-book", "cta-book"].forEach(id => {
  $(id).onclick = bookOrLogin;
});
document.querySelectorAll(".book").forEach(button => {
  button.onclick = bookOrLogin;
});
$("close").onclick = closeAuth;
$("close-bg").onclick = closeAuth;
document.querySelectorAll("[data-tab]").forEach(button => {
  button.onclick = () => showTab(button.dataset.tab);
});

async function loadPublicPricing() {
  try {
    pricingData = await api("/api/pricing");
    const prices = new Map(
      pricingData.vehicle_prices.map(item => [item.vehicle_type, item.price_paise]),
    );
    document.querySelectorAll("[data-price-category]").forEach(element => {
      const price = prices.get(element.dataset.priceCategory);
      element.textContent = price === undefined ? "Price unavailable" : money(price);
    });
    document.querySelectorAll("[data-doorstep-price]").forEach(element => {
      element.textContent = money(pricingData.doorstep_charge_paise);
    });
    $("pricing-status").textContent = "";
    $("booking-mode").options[1].textContent =
      `Doorstep service (+${money(pricingData.doorstep_charge_paise)})`;
    refreshEstimate();
  } catch (error) {
    $("pricing-status").textContent = "Pricing is temporarily unavailable. Please try again shortly.";
    document.querySelectorAll("[data-price-category], [data-doorstep-price]").forEach(element => {
      element.textContent = "Unavailable";
    });
    console.error("Could not load wash pricing:", error);
  }
}

function canonicalCategory(vehicleType) {
  const normalized = vehicleType.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const aliases = {
    bike: "Bike / Scooter",
    "bike scooter": "Bike / Scooter",
    scooter: "Bike / Scooter",
    motorcycle: "Bike / Scooter",
    "two wheeler": "Bike / Scooter",
    hatchback: "Hatchback",
    sedan: "Sedan",
    suv: "SUV / MUV",
    muv: "SUV / MUV",
    "suv muv": "SUV / MUV",
    "luxury suv": "Luxury / Large SUV",
    "large suv": "Luxury / Large SUV",
    "luxury large suv": "Luxury / Large SUV",
  };
  return aliases[normalized] || null;
}

$("register-form").onsubmit = async event => {
  event.preventDefault();
  const password = $("reg-password").value;
  if (password !== $("reg-confirm").value) {
    $("register-message").textContent = "Passwords do not match";
    return;
  }
  try {
    await api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        name: $("reg-name").value.trim(),
        phone: $("reg-phone").value.trim(),
        password,
      }),
    });
    const phone = $("reg-phone").value;
    showTab("login");
    $("login-phone").value = phone;
    $("login-message").textContent = "Account created. Please log in.";
  } catch (error) {
    $("register-message").textContent = error.message;
  }
};

$("login-form").onsubmit = async event => {
  event.preventDefault();
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        phone: $("login-phone").value.trim(),
        password: $("login-password").value,
      }),
    });
    token = data.access_token;
    sessionStorage.setItem(key, token);
    closeAuth();
    await dashboard();
  } catch (error) {
    $("login-message").textContent = error.message;
  }
};

function logout() {
  token = null;
  sessionStorage.removeItem(key);
  $("app-view").classList.add("hidden");
  document.querySelectorAll("body>header,body>main,body>footer").forEach(element => {
    element.classList.remove("hidden");
  });
  window.scrollTo(0, 0);
}

$("logout-btn").onclick = logout;

async function dashboard() {
  try {
    const user = await api("/api/me");
    $("customer-name").textContent = user.name;
    $("profile-name").textContent = user.name;
    $("profile-phone").textContent = user.phone;
    document.querySelectorAll("body>header,body>main,body>footer").forEach(element => {
      element.classList.add("hidden");
    });
    $("app-view").classList.remove("hidden");
    await Promise.all([vehicles(), services(), bookings()]);
  } catch {
    logout();
  }
}

async function vehicles() {
  customerVehicles = await api("/api/vehicles");
  $("booking-vehicle").innerHTML = customerVehicles.map(vehicle =>
    `<option value="${vehicle.id}">${esc(vehicle.make_model)} · ${esc(vehicle.registration_number)} · ${esc(vehicle.vehicle_type)}</option>`,
  ).join("") || '<option value="">Add a vehicle first</option>';
  refreshEstimate();
}

async function services() {
  const availableServices = await api("/api/services");
  $("booking-service").innerHTML = availableServices.map(service =>
    `<option value="${service.id}">${esc(service.name)} · ${service.duration_minutes} min</option>`,
  ).join("");
  refreshEstimate();
}

async function bookings() {
  const customerBookings = await api("/api/bookings");
  $("booking-list").innerHTML = customerBookings.map(booking => {
    const amount = booking.total_price_paise > 0
      ? `<span class="booking-amount">${money(booking.total_price_paise)} total · Wash ${money(booking.service_price_paise)}${booking.doorstep_charge_paise ? ` + Doorstep ${money(booking.doorstep_charge_paise)}` : ""}</span>`
      : '<span class="booking-amount">Price unavailable for this earlier booking</span>';
    return `<div class="booking-row"><b>Booking #${booking.id} · ${booking.service_mode === "doorstep" ? "Doorstep" : "At our shop"}</b><small>${new Date(booking.scheduled_at).toLocaleString()} · ${esc(booking.location_text || "Shop appointment")} · ${esc(booking.status)}</small>${amount}</div>`;
  }).join("") || "No bookings yet.";
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

$("vehicle-form").onsubmit = async event => {
  event.preventDefault();
  try {
    await api("/api/vehicles", {
      method: "POST",
      body: JSON.stringify({
        vehicle_type: $("vehicle-type").value,
        make_model: $("vehicle-model").value,
        registration_number: $("vehicle-reg").value,
      }),
    });
    $("vehicle-message").textContent = "Vehicle saved";
    $("vehicle-form").reset();
    await vehicles();
  } catch (error) {
    $("vehicle-message").textContent = error.message;
  }
};

function refreshEstimate() {
  if (!pricingData) return;
  const vehicle = customerVehicles.find(
    item => String(item.id) === $("booking-vehicle").value,
  );
  const category = vehicle ? canonicalCategory(vehicle.vehicle_type) : null;
  const price = category && pricingData.vehicle_prices.find(
    item => item.vehicle_type === category,
  );
  const categoryUpdate = Boolean(vehicle && !price);
  $("category-update").classList.toggle("hidden", !categoryUpdate);
  if (categoryUpdate && $("category-update-select").options.length > 0) {
    $("category-update-select").value = "";
    $("category-update-message").textContent = "";
  }
  if (!price) {
    $("booking-estimate").textContent = vehicle
      ? "Update this vehicle's category to see its package price."
      : "Select a vehicle to see the estimated price.";
    return;
  }
  const doorstep = $("booking-mode").value === "doorstep"
    ? pricingData.doorstep_charge_paise
    : 0;
  const total = price.price_paise + doorstep;
  const serviceName = $("booking-service").selectedOptions[0]?.textContent || "Steam wash";
  $("booking-estimate").innerHTML =
    `<div><span>Selected wash service</span><b>${esc(serviceName)}</b></div>` +
    `<div><span>Vehicle package</span><b>${money(price.price_paise)}</b></div>` +
    `<div><span>${doorstep ? "Doorstep convenience charge" : "Shop appointment charge"}</span><b>${doorstep ? money(doorstep) : "No additional charge"}</b></div>` +
    `<div class="estimate-total"><span>Estimated total</span><b>${money(total)}</b></div>`;
}

$("booking-vehicle").onchange = refreshEstimate;
$("booking-service").onchange = refreshEstimate;
$("booking-mode").onchange = () => {
  const isDoorstep = $("booking-mode").value === "doorstep";
  $("address-wrap").classList.toggle("hidden", !isDoorstep);
  $("booking-address").required = isDoorstep;
  refreshEstimate();
};

$("category-update-button").onclick = async () => {
  const vehicleId = $("booking-vehicle").value;
  const vehicleType = $("category-update-select").value;
  if (!vehicleId || !vehicleType) {
    $("category-update-message").textContent = "Choose a vehicle category.";
    return;
  }
  try {
    await api(`/api/vehicles/${vehicleId}`, {
      method: "PATCH",
      body: JSON.stringify({ vehicle_type: vehicleType }),
    });
    $("category-update-message").textContent = "Vehicle category updated.";
    await vehicles();
  } catch (error) {
    $("category-update-message").textContent = error.message;
  }
};

$("booking-form").onsubmit = async event => {
  event.preventDefault();
  try {
    await api("/api/bookings", {
      method: "POST",
      body: JSON.stringify({
        vehicle_id: Number($("booking-vehicle").value),
        service_id: Number($("booking-service").value),
        service_mode: $("booking-mode").value,
        location_text: $("booking-mode").value === "doorstep"
          ? $("booking-address").value
          : "",
        scheduled_at: new Date($("booking-date").value).toISOString(),
        notes: $("booking-notes").value,
      }),
    });
    $("booking-message").textContent = "Booking request sent. Our team will confirm.";
    await bookings();
  } catch (error) {
    $("booking-message").textContent = error.message;
  }
};

loadPublicPricing();
if (token) dashboard();
