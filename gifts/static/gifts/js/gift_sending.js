(function () {
    "use strict";

    var modal = document.getElementById("giftOrderModal");
    var form = document.getElementById("giftOrderForm");
    if (!modal || !form) return;

    var successModal = document.getElementById("giftSuccessModal");
    var submitButton = document.getElementById("giftSubmitButton");
    var alertBox = document.getElementById("giftFormAlert");
    var activeCard = null;
    var lastFocused = null;

    function naira(value) {
        return "â‚¦" + parseFloat(value || "0").toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function clearErrors() {
        alertBox.hidden = true;
        alertBox.textContent = "";
        form.querySelectorAll(".gift-field-error").forEach(function (el) {
            el.textContent = "";
        });
        form.querySelectorAll(".gift-control").forEach(function (el) {
            el.classList.remove("has-error");
        });
    }

    function showError(message) {
        alertBox.textContent = message || "We could not place your order. Please try again.";
        alertBox.hidden = false;
        alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function openOrderModal(button) {
        activeCard = button;
        lastFocused = document.activeElement;
        clearErrors();
        form.reset();

        var imageUrl = button.getAttribute("data-image") || "";
        var image = document.getElementById("giftSummaryImage");
        var fallback = document.getElementById("giftSummaryFallback");
        if (imageUrl) {
            image.src = imageUrl;
            image.hidden = false;
            fallback.hidden = true;
        } else {
            image.src = "";
            image.hidden = true;
            fallback.hidden = false;
        }

        document.getElementById("giftSummaryName").textContent = button.getAttribute("data-product-name");
        document.getElementById("giftSummaryPrice").textContent = naira(button.getAttribute("data-price"));
        modal.hidden = false;
        document.body.style.overflow = "hidden";
        setTimeout(function () {
            document.getElementById("recipient_full_name").focus();
        }, 30);
    }

    function closeOrderModal() {
        modal.hidden = true;
        document.body.style.overflow = "";
        activeCard = null;
        if (lastFocused) lastFocused.focus();
    }

    function closeSuccessModal() {
        successModal.hidden = true;
        document.body.style.overflow = "";
    }

    document.querySelectorAll(".gift-send").forEach(function (button) {
        button.addEventListener("click", function () { openOrderModal(button); });
    });

    document.querySelectorAll("[data-close-order]").forEach(function (button) {
        button.addEventListener("click", closeOrderModal);
    });

    modal.addEventListener("click", function (event) {
        if (event.target === modal) closeOrderModal();
    });

    successModal.addEventListener("click", function (event) {
        if (event.target === successModal) closeSuccessModal();
    });
    document.getElementById("giftSuccessClose").addEventListener("click", closeSuccessModal);

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        if (!modal.hidden) closeOrderModal();
        if (!successModal.hidden) closeSuccessModal();
    });

    document.querySelectorAll(".gift-filter").forEach(function (button) {
        button.addEventListener("click", function () {
            document.querySelectorAll(".gift-filter").forEach(function (item) {
                item.classList.remove("active");
            });
            button.classList.add("active");
            var filter = button.getAttribute("data-filter");
            document.querySelectorAll(".gift-section").forEach(function (section) {
                section.hidden = filter !== "all" && section.id !== filter;
            });
        });
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!activeCard || submitButton.disabled) return;
        clearErrors();

        if (!form.checkValidity()) {
            form.reportValidity();
            showError("Please complete all required recipient details.");
            return;
        }

        submitButton.disabled = true;
        submitButton.querySelector("span").textContent = "Placing orderâ€¦";

        fetch(activeCard.getAttribute("data-order-url"), {
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
                        var input = form.querySelector('[name="' + field + '"]');
                        if (target) target.textContent = data.errors[field].join(" ");
                        if (input) input.classList.add("has-error");
                    });
                }
                return;
            }

            var newBalance = naira(data.new_balance);
            document.querySelectorAll(".wallet-amount, .wallet-chip .mono, #giftWalletBalance")
                .forEach(function (element) { element.textContent = newBalance; });

            document.getElementById("giftSuccessOrder").textContent = data.order_id;
            document.getElementById("giftSuccessProduct").textContent = data.product_name;
            closeOrderModal();
            successModal.hidden = false;
            document.body.style.overflow = "hidden";
        })
        .catch(function () {
            showError("Network error. Please check your connection and try again.");
        })
        .finally(function () {
            submitButton.disabled = false;
            submitButton.querySelector("span").textContent = "Confirm & Pay";
        });
    });
})();