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
            // No server picked: lock everything again
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
                var available = (data.services || []).filter(function (s) { return s.available; });

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

    serviceSelect.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        priceDisplay.textContent = naira(opt ? opt.dataset.price : 0);
    });

    requestForm.addEventListener('submit', function (e) {
        var opt = serviceSelect.options[serviceSelect.selectedIndex];
        if (!serverSelect.value || !countrySelect.value || !opt || !opt.value) {
            e.preventDefault();
            return;
        }
        overlay.hidden = false;
        requestBtn.disabled = true;
    });

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

    if (document.querySelector('.bn-waiting')) {
        setTimeout(function () { location.reload(); }, 8000);
    }

});