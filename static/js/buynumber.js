/* PabloExchange — Buy Number: server → country → services → price
   Built-in searchable dropdowns (no external library). */

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

    var openPanels = [];

    function naira(n) {
        return '₦' + parseFloat(n || 0).toLocaleString('en-NG', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    function fireChange(el) {
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function closeAllPanels() {
        openPanels.forEach(function (p) { p.close(); });
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest('.ss-wrapper')) { closeAllPanels(); }
    });

    // ================= Built-in searchable dropdown =================
    function buildSearchable(select, searchPlaceholder) {
        select.classList.add('ss-native');

        var wrapper = document.createElement('div');
        wrapper.className = 'ss-wrapper';
        select.parentNode.insertBefore(wrapper, select.nextSibling);

        var control = document.createElement('button');
        control.type = 'button';
        control.className = 'ss-control';

        var panel = document.createElement('div');
        panel.className = 'ss-panel';
        panel.hidden = true;

        var search = document.createElement('input');
        search.type = 'text';
        search.className = 'ss-search';
        search.placeholder = searchPlaceholder;
        search.setAttribute('autocomplete', 'off');

        var list = document.createElement('div');
        list.className = 'ss-list';

        var emptyMsg = document.createElement('div');
        emptyMsg.className = 'ss-empty';
        emptyMsg.textContent = 'No matches found';
        emptyMsg.hidden = true;

        panel.appendChild(search);
        panel.appendChild(list);
        panel.appendChild(emptyMsg);
        wrapper.appendChild(control);
        wrapper.appendChild(panel);

        var isOpen = false;

        function syncLabel() {
            var label = '';
            if (select.value) {
                for (var i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === select.value) {
                        label = select.options[i].text;
                        break;
                    }
                }
            }
            if (!label && select.options.length) {
                label = select.options[0].text;
            }
            control.textContent = label;
        }

        function syncDisabled() {
            wrapper.classList.toggle('disabled', select.disabled);
        }

        function render(filter) {
            var q = (filter || '').toLowerCase();
            list.innerHTML = '';
            var any = false;
            for (var i = 0; i < select.options.length; i++) {
                var o = select.options[i];
                if (q && o.text.toLowerCase().indexOf(q) === -1) { continue; }
                any = true;
                (function (opt) {
                    var item = document.createElement('div');
                    item.className = 'ss-item' +
                        (opt.value === select.value ? ' selected' : '') +
                        (opt.value === '' ? ' ss-item--clear' : '');
                    item.textContent = opt.text;
                    item.addEventListener('click', function () {
                        select.value = opt.value;
                        fireChange(select);
                        close();
                    });
                    list.appendChild(item);
                })(o);
            }
            emptyMsg.hidden = any;
        }

        function open() {
            if (select.disabled) { return; }
            closeAllPanels();
            search.value = '';
            render('');
            panel.hidden = false;
            isOpen = true;
            wrapper.classList.add('open');
            setTimeout(function () { search.focus(); }, 30);
        }

        function close() {
            if (!isOpen) { return; }
            panel.hidden = true;
            isOpen = false;
            wrapper.classList.remove('open');
        }

        control.addEventListener('click', function () {
            if (isOpen) { close(); } else { open(); }
        });

        search.addEventListener('input', function () {
            render(search.value);
        });

        search.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var first = list.querySelector('.ss-item');
                if (first) { first.click(); }
            } else if (e.key === 'Escape') {
                close();
                control.focus();
            }
        });

        // Keep the visible label in sync with any programmatic changes.
        select.addEventListener('change', syncLabel);

        syncLabel();
        syncDisabled();

        openPanels.push({ close: close });

        return { syncLabel: syncLabel, syncDisabled: syncDisabled };
    }

    var countrySS = buildSearchable(countrySelect, 'Search Country...');
    var serviceSS = buildSearchable(serviceSelect, 'Search Service...');

    // ---------- Thin wrappers around the native selects ----------

    function setCountryEnabled(enabled) {
        countrySelect.disabled = !enabled;
        countrySS.syncDisabled();
    }

    function selectCountryValue(value) {
        countrySelect.value = value;
        countrySS.syncLabel();
        fireChange(countrySelect);
    }

    function clearCountryValue() {
        if (countrySelect.value) {
            countrySelect.value = '';
            fireChange(countrySelect);
        }
        countrySS.syncLabel();
    }

    // opts: [{value, text, price?}] — price optional (live-catalog items)
    function setServiceOptions(opts, enabledAfter) {
        priceMap = {};
        var html = '';
        opts.forEach(function (o) {
            if (o.price) { priceMap[o.value] = o.price; }
            var p = o.price ? ' data-price="' + o.price + '"' : '';
            html += '<option value="' + o.value + '"' + p + '>' + o.text + '</option>';
        });
        serviceSelect.innerHTML = html;
        serviceSelect.value = '';
        serviceSelect.disabled = !enabledAfter;
        serviceSS.syncDisabled();
        serviceSS.syncLabel();
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
            // Server 1 = USA only: lock country to US. fireChange runs the
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