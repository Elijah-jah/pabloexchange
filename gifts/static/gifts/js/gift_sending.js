
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

    var MAX_IMAGES = 5;
    var MAX_IMAGE_SIZE = 5 * 1024 * 1024;    // per-photo cap after compression
    var MAX_SOURCE_SIZE = 25 * 1024 * 1024;  // reject absurdly large originals
    var MAX_PHOTO_DIMENSION = 2000;          // longest side after compression
    var JPEG_QUALITY = 0.85;

    var imageInput = document.getElementById("gift_images");
    var uploadArea = document.getElementById("giftUploadArea");
    var uploadButton = document.getElementById("giftUploadButton");
    var uploadHint = document.getElementById("giftUploadHint");
    var uploadPreviews = document.getElementById("giftUploadPreviews");
    var selectedImages = null; // DataTransfer holding the pending photos
    var optimizing = false;

    var DEFAULT_HINT = "JPG, PNG or WEBP — up to " + MAX_IMAGES +
        " photos. They are compressed automatically for a fast upload.";

    function newImageBucket() {
        try {
            return new DataTransfer();
        } catch (error) {
            return null; // very old browsers: fall back to the raw input files
        }
    }

    function naira(value) {
        return "₦" + parseFloat(value || "0").toLocaleString("en-US", {
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
        if (uploadArea) uploadArea.classList.remove("has-error");
    }

    function showError(message) {
        alertBox.textContent = message || "We could not place your order. Please try again.";
        alertBox.hidden = false;
        alertBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function currentImageFiles() {
        if (selectedImages) return Array.prototype.slice.call(selectedImages.files);
        return imageInput ? Array.prototype.slice.call(imageInput.files || []) : [];
    }

    // Compress one photo in the browser: max 2000px on the longest side,
    // re-encoded as JPEG. Falls back to the original file if anything fails.
    function compressImage(file) {
        return new Promise(function (resolve) {
            if (!file.type || file.type.indexOf("image/") !== 0 || file.size > MAX_SOURCE_SIZE) {
                resolve(file); // validation below reports the problem
                return;
            }
            if (file.type === "image/jpeg" && file.size <= 1024 * 1024) {
                resolve(file); // already small enough — skip re-encoding
                return;
            }
            var url = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function () {
                URL.revokeObjectURL(url);
                var scale = Math.min(1, MAX_PHOTO_DIMENSION / Math.max(img.width, img.height));
                var canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(img.width * scale));
                canvas.height = Math.max(1, Math.round(img.height * scale));
                var ctx = canvas.getContext("2d");
                ctx.fillStyle = "#ffffff"; // flatten transparency onto white
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                canvas.toBlob(function (blob) {
                    if (!blob) { resolve(file); return; }
                    var name = (file.name || "photo").replace(/\.[^.]+$/, "") + ".jpg";
                    resolve(new File([blob], name, { type: "image/jpeg" }));
                }, "image/jpeg", JPEG_QUALITY);
            };
            img.onerror = function () {
                URL.revokeObjectURL(url);
                resolve(file);
            };
            img.src = url;
        });
    }

    function refreshUploadUI() {
        if (!uploadPreviews) return;
        var files = currentImageFiles();
        uploadPreviews.innerHTML = "";
        uploadPreviews.hidden = files.length === 0;

        files.forEach(function (file, index) {
            var thumb = document.createElement("div");
            thumb.className = "gift-upload-thumb";

            var img = document.createElement("img");
            img.alt = file.name;
            img.src = URL.createObjectURL(file);
            img.onload = function () { URL.revokeObjectURL(img.src); };

            var remove = document.createElement("button");
            remove.type = "button";
            remove.className = "gift-upload-remove";
            remove.setAttribute("aria-label", "Remove " + file.name);
            remove.innerHTML = '<i class="bi bi-x"></i>';
            remove.addEventListener("click", function () { removeImage(index); });

            thumb.appendChild(img);
            thumb.appendChild(remove);
            uploadPreviews.appendChild(thumb);
        });

        if (uploadHint && !optimizing) {
            if (files.length === 0) {
                uploadHint.textContent = DEFAULT_HINT;
            } else {
                uploadHint.textContent = files.length + " of " + MAX_IMAGES +
                    " photos selected — compressed and ready.";
            }
        }
    }

    function syncInputFiles() {
        if (selectedImages && imageInput) imageInput.files = selectedImages.files;
        refreshUploadUI();
    }

    function removeImage(index) {
        if (!selectedImages) return; // fallback mode cannot edit the selection
        var next = newImageBucket();
        currentImageFiles().forEach(function (file, i) {
            if (i !== index) next.items.add(file);
        });
        selectedImages = next;
        syncInputFiles();
    }

    function showImageError(message) {
        var target = form.querySelector('[data-field="images"]');
        if (target) target.textContent = message;
        if (uploadArea) {
            uploadArea.classList.add("has-error");
            uploadArea.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }

    function handleImageSelection(fileList) {
        clearErrors();
        var incoming = Array.prototype.slice.call(fileList || []);
        if (incoming.length === 0) return;

        // Compress while the customer fills the rest of the form, so the
        // actual order submission is fast.
        optimizing = true;
        submitButton.disabled = true;
        if (uploadHint) uploadHint.textContent = "Optimizing photos for faster upload…";

        Promise.all(incoming.map(compressImage)).then(function (processed) {
            optimizing = false;
            submitButton.disabled = false;

            var existing = currentImageFiles();
            var accepted = [];
            var rejected = [];

            processed.forEach(function (file, i) {
                var original = incoming[i];
                if (original.size > MAX_SOURCE_SIZE) {
                    rejected.push(original.name + " is too large (over 25 MB).");
                } else if (file.type && file.type.indexOf("image/") !== 0) {
                    rejected.push(file.name + " is not an image.");
                } else if (file.size > MAX_IMAGE_SIZE) {
                    rejected.push(file.name + " could not be reduced below 5 MB.");
                } else {
                    accepted.push(file);
                }
            });

            var combined = existing.concat(accepted);
            if (combined.length > MAX_IMAGES) {
                var room = Math.max(0, MAX_IMAGES - existing.length);
                rejected.push("You can attach at most " + MAX_IMAGES + " photos.");
                accepted = accepted.slice(0, room);
                combined = existing.concat(accepted);
            }

            if (selectedImages) {
                selectedImages = newImageBucket();
                combined.forEach(function (file) { selectedImages.items.add(file); });
                syncInputFiles();
            } else {
                refreshUploadUI(); // fallback: browser keeps whatever was picked
            }

            if (rejected.length > 0) showImageError(rejected.join(" "));
        });
    }

    function resetImages() {
        selectedImages = newImageBucket();
        if (imageInput) imageInput.value = "";
        optimizing = false;
        submitButton.disabled = false;
        refreshUploadUI();
    }

    if (imageInput && uploadButton) {
        uploadButton.addEventListener("click", function () { imageInput.click(); });
        if (uploadArea) {
            uploadArea.addEventListener("click", function (event) {
                if (event.target === uploadArea || event.target === uploadHint) imageInput.click();
            });
        }
        imageInput.addEventListener("change", function () {
            handleImageSelection(imageInput.files);
        });
        selectedImages = newImageBucket();
    }

    function openOrderModal(button) {
        activeCard = button;
        lastFocused = document.activeElement;
        clearErrors();
        form.reset();
        resetImages();

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

        if (optimizing) {
            showError("Please wait a moment — your photos are still being optimized.");
            return;
        }

        if (!form.checkValidity()) {
            form.reportValidity();
            showError("Please complete all required recipient details.");
            return;
        }

        submitButton.disabled = true;
        submitButton.querySelector("span").textContent = "Placing order…";

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
                        if (input && input.type === "file") {
                            if (uploadArea) uploadArea.classList.add("has-error");
                        } else if (input) {
                            input.classList.add("has-error");
                        }
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
