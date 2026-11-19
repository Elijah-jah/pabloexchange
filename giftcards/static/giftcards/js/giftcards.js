
/* PabloExchange Gift Cards - store filters + purchase page */
(function () {
    "use strict";

    function naira(value) {
        return "\u20A6" + parseFloat(value || "0").toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function dollars(value) {
        return "$" + parseFloat(value || "0").toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    /* ================= STORE PAGE: search + country + category filters ================= */
    var grid = document.getElementById("gcGrid");
    if (grid) {
        var searchInput = document.getElementById("gcSearch");
        var noMatch = document.getElementById("gcNoMatch");
        var activeCountry = "all";
        var activeCategory = "all";

        function applyFilters() {
            var term = (searchInput.value || "").trim().toLowerCase();
            var visible = 0;

            grid.querySelectorAll(".gc-card").forEach(function (card) {
                var countryOk = activeCountry === "all" || card.getAttribute("data-country") === activeCountry;
                var categoryOk = activeCategory === "all" || card.getAttribute("data-category") === activeCategory;
                var searchOk = !term || card.getAttribute("data-name").indexOf(term) !== -1;
                var show = countryOk && categoryOk && searchOk;
                card.hidden = !show;
                if (show) visible++;
            });

            if (noMatch) noMatch.hidden = visible !== 0;
            grid.hidden = visible === 0;
        }

        document.querySelectorAll("#gcCountryFilters .gc-filter").forEach(function (button) {
            button.addEventListener("click", function () {
                document.querySelectorAll("#gcCountryFilters .gc-filter").forEach(function (item) {
                    item.classList.remove("active");
                });
                button.classList.add("active");
                activeCountry = button.getAttribute("data-country");
                applyFilters();
            });
        });

        document.querySelectorAll("#gcCategoryFilters .gc-filter").forEach(function (button) {
            button.addEventListener("click", function () {
                document.querySelectorAll("#gcCategoryFilters .gc-filter").forEach(function (item) {
                    item.classList.remove("active");
                });
                button.classList.add("active");
                activeCategory = button.getAttribute("data-category");
                applyFilters();
            });
        });

        if (searchInput) searchInput.addEventListener("input", applyFilters);
    }

    /* ================= DETAIL PAGE: live total + purchase ================= */
    var detail = document.getElementById("gcDetail");
    if (!detail) return;

    var form = document.getElementById("gcBuyForm");
    var amountInput = document.getElementById("gcAmount");
    var qtyInput = document.getElementById("gcQty");
    var buyerInput = document.getElementById("gcBuyerName");
    var buyButton = document.getElementById("gcBuyButton");
    var alertBox = document.getElementById("gcFormAlert");
    var successModal = document.getElementById("gcSuccessModal");

    var rate = parseFloat(detail.getAttribute("data-rate")) || 0;
    var minAmount = parseFloat(detail.getAttribute("data-min")) || 0;
    var maxAmount = parseFloat(detail.getAttribute("data-max")) || 0;
    var balance = parseFloat(detail.getAttribute("data-balance")) || 0;

    function currentAmount() {
        var value = parseFloat(amountInput.value);
        return isNaN(value) ? 0 : value;
    }

    function currentQty() {
        var value = parseInt(qtyInput.value, 10);
        if (isNaN(value) || value < 1) return 1;
        if (value > 99) return 99;
        return value;
    }

    function currentTotal() {
        return currentAmount() * currentQty() * rate;
    }

    function clearErrors() {
        alertBox.hidden = true;
        alertBox.textContent = "";
        form.querySelectorAll(".gc-field-error").forEach(function (el) { el.textContent = ""; });
    }

    function showError(message) {
        alertBox.textContent = message || "We could not complete your purchase. Please try again.";
        alertBox.hidden = false;
        alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function refreshSummary() {
        var amount = currentAmount();
        var qty = currentQty();
        var total = currentTotal();

        document.getElementById("gcCardValue").textContent = dollars(amount);
        document.getElementById("gcQtyEcho").textContent = qty;
        document.getElementById("gcTotal").textContent = naira(total);

        var insufficient = total > 0 && total > balance;
        document.getElementById("gcInsufficient").hidden = !insufficient;

        var valid = amount >= minAmount && amount <= maxAmount && qty >= 1 && !insufficient;
        buyButton.disabled = !valid;
    }

    amountInput.addEventListener("input", refreshSummary);
    buyerInput.addEventListener("input", clearErrors);

    qtyInput.addEventListener("input", refreshSummary);
    qtyInput.addEventListener("change", function () {
        qtyInput.value = currentQty();
        refreshSummary();
    });

    document.getElementById("gcQtyMinus").addEventListener("click", function () {
        qtyInput.value = Math.max(1, currentQty() - 1);
        refreshSummary();
    });
    document.getElementById("gcQtyPlus").addEventListener("click", function () {
        qtyInput.value = Math.min(99, currentQty() + 1);
        refreshSummary();
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (buyButton.disabled) return;
        clearErrors();

        var amount = currentAmount();
        if (amount < minAmount || amount > maxAmount) {
            showError("Amount must be between " + dollars(minAmount) + " and " + dollars(maxAmount) + ".");
            return;
        }
        if (!(buyerInput.value || "").trim()) {
            showError("Please enter your name.");
            buyerInput.focus();
            return;
        }

        buyButton.disabled = true;
        buyButton.querySelector("span").textContent = "Processing\u2026";

        fetch(detail.getAttribute("data-purchase-url"), {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            var data = result.data;
            if (!result.ok || !data.success) {
                showError(data.error);
                if (data.errors) {
                    Object.keys(data.errors).forEach(function (field) {
                        var target = form.querySelector('[data-field="' + field + '"]');
                        if (target) target.textContent = data.errors[field].join(" ");
                    });
                }
                return;
            }

            // Keep every wallet display on the page in sync.
            balance = parseFloat(data.new_balance) || 0;
            var newBalance = naira(data.new_balance);
            document.querySelectorAll(".wallet-amount, .wallet-chip .mono, #gcBalance, #gcWalletBalance")
                .forEach(function (element) { element.textContent = newBalance; });

            document.getElementById("gcSuccessOrder").textContent = data.order_id;
            document.getElementById("gcSuccessCard").textContent = data.card_name;
            document.getElementById("gcSuccessBuyer").textContent = data.buyer_name;
            document.getElementById("gcSuccessAmount").textContent = dollars(data.amount_usd);
            document.getElementById("gcSuccessQty").textContent = data.quantity;
            document.getElementById("gcSuccessTotal").textContent = naira(data.total_ngn);
            document.getElementById("gcWhatsappBtn").href = data.whatsapp_url;

            successModal.hidden = false;
            document.body.style.overflow = "hidden";
        })
        .catch(function () {
            showError("Network error. Please check your connection and try again.");
        })
        .finally(function () {
            buyButton.querySelector("span").textContent = "Purchase card now";
            refreshSummary();
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !successModal.hidden) {
            successModal.hidden = true;
            document.body.style.overflow = "";
        }
    });

    refreshSummary();
})();
