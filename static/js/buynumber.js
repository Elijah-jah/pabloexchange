/* PabloExchange — Buy Number: server → country → services → price
   Built-in searchable dropdowns (no external library).
   OTP polling: every waiting order, code shown instantly without reload. */

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

    // Guards against double-reloads when several timers hit 00:00 together.
    var expiredReloaded = false;

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
    // opts.search: false hides the search input (for tiny lists like server)
    // opts.controlClass: extra class on the control (e.g. server styling)
    function buildSearchable(select, searchPlaceholder, opts) {
        opts = opts || {};
        var showSearch = opts.search !== false;

        select.classList.add('ss-native');

        var wrapper = document.createElement('div');
        wrapper.className = 'ss-wrapper';
        select.parentNode.insertBefore(wrapper, select.nextSibling);

        var control = document.createElement('button');
        control.type = 'button';
        control.className = 'ss-control' + (opts.controlClass ? ' ' + opts.controlClass : '');

        var panel = document.createElement('div');
        panel.className = 'ss-panel';
        panel.hidden = true;

        var search = document.createElement('input');
        search.type = 'text';
        search.className = 'ss-search';
        search.placeholder = searchPlaceholder;
        search.setAttribute('autocomplete', 'off');
        if (!showSearch) { search.style.display = 'none'; }

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
            if (showSearch) {
                setTimeout(function () { search.focus(); }, 30);
            }
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

    // Server gets the same widget, no search box, and its bold green styling
    var serverSS = buildSearchable(serverSelect, '', {
        search: false,
        controlClass: 'ss-control--server'
    });
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
    // The timer IS the card's lifetime: when it hits 00:00 we reload, and
    // the buy view excludes expired orders — card gone.
    document.querySelectorAll('.bn-timer').forEach(function (el) {
        var expires = new Date(el.dataset.expires).getTime();
        if (isNaN(expires)) return;
        function tick() {
            var left = Math.max(0, expires - Date.now());
            var m = Math.floor(left / 60000);
            var s = Math.floor((left % 60000) / 1000);
            el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
            if (left <= 0) {
                clearInterval(iv);
                if (!expiredReloaded) {
                    expiredReloaded = true;
                    location.reload();  // server drops the expired card
                }
            }
        }
        tick();
        var iv = setInterval(tick, 1000);
    });

    // ---------- Cancel (styled confirmation modal) ----------
    var cancelModal = document.getElementById('cancelModal');
    var cancelModalYes = document.getElementById('cancelModalYes');
    var cancelModalNo = document.getElementById('cancelModalNo');
    var pendingCancelForm = null;

    function openCancelModal(form) {
        pendingCancelForm = form;
        cancelModal.hidden = false;
    }

    function closeCancelModal() {
        pendingCancelForm = null;
        cancelModal.hidden = true;
    }

    cancelModalYes.addEventListener('click', function () {
        if (pendingCancelForm) {
            overlay.hidden = false;
            document.getElementById('bnOverlayText').textContent = 'Cancelling order…';
            // native submit() bypasses this listener (no re-intercept loop)
            pendingCancelForm.submit();
        }
        closeCancelModal();
    });

    cancelModalNo.addEventListener('click', closeCancelModal);

    // click the dark backdrop to dismiss
    cancelModal.addEventListener('click', function (e) {
        if (e.target === cancelModal) { closeCancelModal(); }
    });

    // Escape closes the modal
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !cancelModal.hidden) { closeCancelModal(); }
    });

    // intercept every cancel form: ask first, never submit directly
    document.querySelectorAll('.bn-cancel-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            openCancelModal(form);
        });
    });

    // ---------- Silent poll: every waiting order, code shown WITHOUT reload ----------
    // ASAP behaviour:
    //   • polls ALL .bn-waiting cards every 5s while the tab is visible
    //   • the moment a code lands, the card updates IN PLACE — no page reload,
    //     so server/country/service selections are preserved
    //   • when the user returns to a backgrounded tab, it polls instantly
    //     (browsers throttle hidden-tab timers, so we catch up on visibility)
    var WAITING_POLL_MS = 5000;
    var pollTimer = null;

    function hasWaitingCards() {
        return document.querySelectorAll('.bn-session.bn-waiting').length > 0;
    }

    function pollWaitingOrders() {
        if (!hasWaitingCards()) {
            if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
            return;
        }

        document.querySelectorAll('.bn-session.bn-waiting').forEach(function (card) {
            var input = card.querySelector('.bn-cancel-form input[name="order_id"]');
            if (!input) return;
            var orderId = input.value;

            fetch('/order/' + orderId + '/status/')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.status === 'active' && !data.otp) return;  // still waiting

                    // ---- Code landed (or order finished): update THIS card in place ----
                    card.classList.remove('bn-waiting');

                    var otpBox = card.querySelector('.bn-otp-box');
                    if (otpBox && data.otp) {
                        otpBox.textContent = data.otp;
                        otpBox.classList.add('has-code');
                    }

                    var statusLine = card.querySelector('.bn-status-line');
                    if (statusLine) {
                        statusLine.classList.add('bn-status-line--done');
                        statusLine.innerHTML =
                            '<span class="bn-status-dot bn-status-dot--done"></span> ' +
                            'Code received — card disappears when the timer ends.';
                    }

                    // delivered/finished orders can no longer be cancelled
                    var cancelForm = card.querySelector('.bn-cancel-form');
                    if (cancelForm) { cancelForm.remove(); }

                    // ping the user even if they're on another tab
                    if (document.hidden && 'Notification' in window &&
                        Notification.permission === 'granted') {
                        new Notification('PabloExchange',
                            { body: 'Your code arrived: ' + (data.otp || 'check your order') });
                    }

                    if (!hasWaitingCards() && pollTimer) {
                        clearInterval(pollTimer);
                        pollTimer = null;
                    }
                })
                .catch(function () { /* network blip — next tick retries */ });
        });
    }

    if (hasWaitingCards()) {
        pollTimer = setInterval(pollWaitingOrders, WAITING_POLL_MS);

        // catch up instantly the moment the user returns to this tab
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) { pollWaitingOrders(); }
        });

        // ask once so the arrival notification can fire
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

});