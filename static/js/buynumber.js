/* PabloExchange — Buy Number: server → country → services → price */

document.addEventListener('DOMContentLoaded', function () {

    var serverSelect = document.getElementById('serverSelect');
    var countrySelect = document.getElementById('countrySelect');
    var serviceSelect = document.getElementById('serviceSelect');
    var priceDisplay = document.getElementById('priceDisplay');
    var serverHint = document.getElementById('serverHint');
    var requestForm = document.getElementById('requestNumberForm');
    var requestBtn = document.getElementById('requestBtn');
    var overlay = document.getElementById('bnOverlay');

    var SERVER_HINTS = {
        daisysms: 'USA numbers only. Cheapest & fastest delivery.',
        instantnums: 'All countries supported. Pick any country below.'
    };

    function naira(n) {
        return '₦' + parseFloat(n || 0).toLocaleString('en-NG', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    function resetServices(msg) {
        serviceSelect.innerHTML = '<option value="">' + msg + '</option>';
        serviceSelect.disabled = true;
        priceDisplay.textContent = naira(0);
    }

    // ---------- Server changed → set up country, then load services ----------
    serverSelect.addEventListener('change', function () {
        var server = this.value;
        serverHint.textContent = server ? (SERVER_HINTS[server] || '') : '';

        if (!server) {
            countrySelect.value = '';
            countrySelect.disabled = true;
            resetServices('Select Server First');
            return;
        }

        countrySelect.disabled = false;
        countrySelect.value = '';

        if (server === 'daisysms') {
            // Server 1 = USA only: lock country to US
            countrySelect.value = 'US';
            countrySelect.disabled = true;
            loadServices('US', server);
        } else {
            resetServices('Select Country');
        }
    });

    // ---------- Country selected → fetch services for that server ----------
    countrySelect.addEventListener('change', function () {
        var code = this.value;
        if (!code) { resetServices('Select Country First'); return; }
        loadServices(code, serverSelect.value);
    });

    function loadServices(code, server) {
        serviceSelect.innerHTML = '<option value="">Loading…</option>';
        serviceSelect.disabled = true;
        priceDisplay.textContent = naira(0);

        fetch('/pricing/for-country/' + encodeURIComponent(code) + '/?server=' + encodeURIComponent(server))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                // Available = flag not explicitly false AND has a price.
                // (Some API responses omit the 'available' key entirely.)
                var available = (data.services || []).filter(function (s) {
                    return s.available !== false && s.price;
                });

                if (!available.length) {
                    resetServices('No services available for this country yet');
                    return;
                }

                var opts = ['<option value="">Select Service</option>'];
                available.forEach(function (s) {
                    opts.push('<option value="' + s.code + '" data-price="' + s.price + '">'
                              + s.name + '</option>');
                });
                serviceSelect.innerHTML = opts.join('');
                serviceSelect.disabled = false;
            })
            .catch(function () {
                resetServices('Failed to load — try again');
            });
    }

    // ---------- Service selected → show price ----------
    serviceSelect.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        priceDisplay.textContent = naira(opt ? opt.dataset.price : 0);
    });

    // ---------- Submit → show overlay ----------
    requestForm.addEventListener('submit', function (e) {
        var opt = serviceSelect.options[serviceSelect.selectedIndex];
        if (!serverSelect.value || !countrySelect.value || !opt || !opt.value) {
            e.preventDefault();
            return;
        }
        // Disabled fields are NOT submitted by the browser — re-enable so
        // the locked "US" value for DaisySMS actually reaches the server.
        countrySelect.disabled = false;
        overlay.hidden = false;
        requestBtn.disabled = true;
    });

    // ---------- Copy buttons ----------
    document.querySelectorAll('.bn-copy-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var value = (btn.dataset.copy || '').trim();
            if (!value) return;
            var done = function () {
                btn.classList.add('copied');
                setTimeout(function () { btn.classList.remove('copied'); }, 1500);
            };
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(value).then(done).catch(function () { fallback(value, done); });
            } else { fallback(value, done); }
        });
    });

    function fallback(text, done) {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        ta.remove(); done();
    }

    // ---------- Countdown timers ----------
    document.querySelectorAll('.bn-timer').forEach(function (el) {
        var expires = new Date(el.dataset.expires).getTime();
        if (isNaN(expires)) return;
        function tick() {
            var left = Math.max(0, expires - Date.now());
            var m = Math.floor(left / 60000);
            var s = Math.floor((left % 60000) / 1000);
            el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
            if (left <= 0) { el.textContent = '00:00'; clearInterval(iv); }
        }
        tick();
        var iv = setInterval(tick, 1000);
    });

    // ---------- Cancel ----------
    document.querySelectorAll('.bn-cancel-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm('Cancel this order? You will not be charged.')) {
                e.preventDefault();
                return;
            }
            overlay.hidden = false;
            document.getElementById('bnOverlayText').textContent = 'Cancelling order…';
        });
    });

    // ---------- Silent poll while waiting for SMS (no more 8s reloads) ----------
    // The server-side APScheduler sweep delivers the SMS whether this page
    // is open or not — this just refreshes the page ONCE when it lands.
    var waitingEl = document.querySelector('.bn-waiting');
    if (waitingEl) {
        // order id is already on the page inside the cancel form's input
        var orderInput = document.querySelector('.bn-cancel-form input[name="order_id"]');
        var orderId = orderInput ? orderInput.value : null;
        if (orderId) {
            var poll = setInterval(function () {
                fetch('/smsmarket/order/' + orderId + '/status/')
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.status !== 'active') {
                            clearInterval(poll);
                            location.reload();  // one refresh, only when code lands
                        }
                    })
                    .catch(function () { /* network blip — try again in 10s */ });
            }, 10000);
        }
    }

});