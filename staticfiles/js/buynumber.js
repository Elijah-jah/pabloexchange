/* PabloExchange — Buy Number: country→services fetch, price, timers, copy, cancel, overlay */

document.addEventListener('DOMContentLoaded', function () {

    var countrySelect = document.getElementById('countrySelect');
    var serviceSelect = document.getElementById('serviceSelect');
    var priceDisplay = document.getElementById('priceDisplay');
    var requestForm = document.getElementById('requestNumberForm');
    var requestBtn = document.getElementById('requestBtn');
    var overlay = document.getElementById('bnOverlay');

    function naira(n) {
        return '₦' + parseFloat(n || 0).toLocaleString('en-NG', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    // ---------- Country selected → fetch ALL services with availability flags ----------
    countrySelect.addEventListener('change', function () {
        var code = this.value;
        serviceSelect.innerHTML = '<option value="">Loading…</option>';
        serviceSelect.disabled = true;
        priceDisplay.textContent = naira(0);

        if (!code) {
            serviceSelect.innerHTML = '<option value="">Select Country First</option>';
            return;
        }

        fetch('/pricing/for-country/' + encodeURIComponent(code) + '/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.services.length) {
                    serviceSelect.innerHTML = '<option value="">No services for this country</option>';
                    return;
                }
                var opts = ['<option value="">Select Service</option>'];
                data.services.forEach(function (s) {
                    if (s.available) {
                        opts.push('<option value="' + s.code + '" data-price="' + s.price + '">'
                                  + s.name + '</option>');
                    } else {
                        opts.push('<option value="' + s.code + '" data-available="0" disabled>'
                                  + s.name + ' — Unavailable</option>');
                    }
                });
                serviceSelect.innerHTML = opts.join('');
                serviceSelect.disabled = false;
            })
            .catch(function () {
                serviceSelect.innerHTML = '<option value="">Failed to load — pick country again</option>';
            });
    });

    // ---------- Service selected → show price ----------
    serviceSelect.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        priceDisplay.textContent = naira(opt ? opt.dataset.price : 0);
    });

    // ---------- Submit → block unavailable, then show overlay ----------
    requestForm.addEventListener('submit', function (e) {
        var opt = serviceSelect.options[serviceSelect.selectedIndex];
        if (!opt || !opt.value || opt.dataset.available === '0') {
            e.preventDefault();
            return;
        }
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

    // ---------- Cancel: confirm + overlay ----------
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

    // ---------- Auto-refresh while waiting for SMS (every 8s, only if any waiting) ----------
    if (document.querySelector('.bn-waiting')) {
        setTimeout(function () { location.reload(); }, 8000);
    }

});