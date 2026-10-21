/* PabloExchange — Buy Number: server → country → services → price
   Country & Service dropdowns use TomSelect (searchable) when available,
   and degrade to plain native selects if the CDN is unreachable. */

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

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

    // service code -> price (DB-priced rows known up front; live ones filled
    // in on selection and remembered for the session)
    var priceMap = {};

    function naira(n) {
        return '₦' + parseFloat(n || 0).toLocaleString('en-NG', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    function fireChange(el) {
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // ---------- Searchable dropdowns (optional enhancement) ----------
    var countryTS = null;
    var serviceTS = null;

    if (typeof TomSelect !== 'undefined') {
        try {
            countryTS = new TomSelect(countrySelect, {
                maxOptions: 300,
                allowEmptyOption: true,
                placeholder: 'Select Country',
                dropdownClass: 'bn-ts-dropdown',
                controlInput: '<input type="text" autocomplete="off" placeholder="Search Country...">'
            });
            serviceTS = new TomSelect(serviceSelect, {
                maxOptions: 2000,
                allowEmptyOption: true,
                placeholder: 'Select Service',
                dropdownClass: 'bn-ts-dropdown',
                controlInput: '<input type="text" autocomplete="off" placeholder="Search Service...">'
            });
        } catch (e) {
            // TomSelect exists but failed on these elements — run native.
            countryTS = null;
            serviceTS = null;
        }
    }

    // ---------- Thin wrappers so both modes share one code path ----------

    function setCountryEnabled(enabled) {
        if (countryTS) {
            if (enabled) { countryTS.enable(); } else { countryTS.disable(); }
        } else {
            countrySelect.disabled = !enabled;
        }
    }

    function selectCountryValue(value) {
        if (countryTS) {
            countryTS.setValue(value);            // fires change
        } else {
            countrySelect.value = value;
            fireChange(countrySelect);
        }
    }

    function clearCountryValue() {
        if (countryTS) {
            countryTS.clear();                    // fires change if value changes
        } else if (countrySelect.value) {
            countrySelect.value = '';
            fireChange(countrySelect);
        }
    }

    // opts: [{value, text, price?}] — price optional (live-catalog items)
    function setServiceOptions(opts, enabledAfter) {
        priceMap = {};
        var html = '';
        var tsOpts = [];
        opts.forEach(function (o) {
            if (o.price) { priceMap[o.value] = o.price; }
            var p = o.price ? ' data-price="' + o.price + '"' : '';
            html += '<option value="' + o.value + '"' + p + '>' + o.text + '</option>';
            tsOpts.push({ value: o.value, text: o.text });
        });

        if (serviceTS) {
            serviceTS.clearOptions();
            serviceTS.addOption(tsOpts);
            serviceTS.refreshOptions(false);
            serviceTS.setValue('');
            if (enabledAfter) { serviceTS.enable(); } else { serviceTS.disable(); }
        } else {
            serviceSelect.innerHTML = html;
            serviceSelect.value = '';
            serviceSelect.disabled = !enabledAfter;
        }
        priceDisplay.textContent = naira(0);
    }

    function resetServices(msg) {
        setServiceOptions([{ value: '', text: msg }], false);
    }

    // ---------- Server changed → set up country, then load services ----------
    serverSelect.addEventListener('change', function () {
        var server = this.value;
        serverHint.textContent = server ? (SERVER_HINTS[server] || '') : '';

        if (!server) {
            clearCountryValue();
            setCountryEnabled(false);
            resetServices('Select Server First');
            return;
        }

        setCountryEnabled(true);
        clearCountryValue();  // fires change → resets the service list

        if (server === 'daisysms') {
            // Server 1 = USA only: lock country to US. setValue fires the
            // country change handler, which loads the services.
            selectCountryValue('US');
            setCountryEnabled(false);  // keep it visually locked
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
        setServiceOptions([{ value: '', text: 'Loading…' }], false);

        fetch('/pricing/for-country/' + encodeURIComponent(code) + '/?server=' + encodeURIComponent(server))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                // Available = flag not explicitly false. Price may be absent
                // for live-catalog items — fetched on selection.
                var available = (data.services || []).filter(function (s) {
                    return s.available !== false && s.price !== undefined;
                });

                if (!available.length) {
                    resetServices('No services available for this country yet');
                    return;
                }

                var opts = [{ value: '', text: 'Select Service' }];
                available.forEach(function (s) {
                    opts.push({ value: s.code, text: s.name, price: s.price });
                });
                setServiceOptions(opts, true);
            })
            .catch(function () {
                resetServices('Failed to load — try again');
            });
    }

    // ---------- Service selected → show price (fetch live if needed) ----------
    serviceSelect.addEventListener('change', function () {
        var code = this.value;
        if (!code) { priceDisplay.textContent = naira(0); return; }

        if (priceMap[code]) {
            priceDisplay.textContent = naira(priceMap[code]);
            return;
        }
        priceDisplay.textContent = 'Checking…';
        fetch('/pricing/check-price/?service=' + encodeURIComponent(code)
              + '&country=' + encodeURIComponent(countrySelect.value)
              + '&server=' + encodeURIComponent(serverSelect.value))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.available) {
                    priceMap[code] = data.price;
                    priceDisplay.textContent = naira(data.price);
                } else {
                    priceDisplay.textContent = 'Unavailable for this country';
                }
            })
            .catch(function () { priceDisplay.textContent = '—'; });
    });

    // ---------- Submit → show overlay ----------
    requestForm.addEventListener('submit', function (e) {
        if (!serverSelect.value || !countrySelect.value || !serviceSelect.value) {
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
    var waitingEl = document.querySelector('.bn-waiting');
    if (waitingEl) {
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