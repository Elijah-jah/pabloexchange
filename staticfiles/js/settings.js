/* PabloExchange — settings: tabs + AJAX saves */

document.addEventListener('DOMContentLoaded', function () {

    const toast = document.getElementById('setToast');
    let toastTimer;

    function showToast(message, isError) {
        clearTimeout(toastTimer);
        toast.textContent = message;
        toast.className = 'set-toast show' + (isError ? ' error' : '');
        toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
    }

    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return m ? decodeURIComponent(m[2]) : '';
    }

    // ---------- Tabs ----------
    document.querySelectorAll('.set-tab').forEach(tab => {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.set-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.set-panel').forEach(p => p.hidden = true);
            this.classList.add('active');
            document.getElementById('panel-' + this.dataset.tab).hidden = false;
        });
    });

    // ---------- AJAX forms ----------
    document.querySelectorAll('.set-form').forEach(form => {
        const action = form.dataset.action;
        const isToggle = form.classList.contains('set-toggle-form');

        async function submit() {
            const btn = form.querySelector('.set-btn');
            const text = btn ? btn.querySelector('.submit-text') : null;
            const spinner = btn ? btn.querySelector('.submit-spinner') : null;
            if (btn) btn.disabled = true;
            if (text) text.style.display = 'none';
            if (spinner) spinner.style.display = 'inline-flex';

            try {
                const resp = await fetch('', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: new FormData(form),
                });
                const data = await resp.json();

                if (data.ok) {
                    showToast(data.message || 'Saved.');
                    if (action === 'password') form.reset();
                } else {
                    showToast(data.error || 'Something went wrong.', true);
                }
            } catch {
                showToast('Network error — try again.', true);
            } finally {
                if (btn) btn.disabled = false;
                if (text) text.style.display = '';
                if (spinner) spinner.style.display = 'none';
            }
        }

        if (isToggle) {
            form.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.addEventListener('change', submit);
            });
        } else {
            form.addEventListener('submit', function (e) {
                e.preventDefault();

                if (action === 'profile') {
                    const u = form.querySelector('[name="username"]').value.trim();
                    if (!u || u.length < 3) {
                        showToast('Username must be at least 3 characters.', true);
                        return;
                    }
                }

                if (action === 'password') {
                    const p1 = form.querySelector('[name="new_password1"]').value;
                    const p2 = form.querySelector('[name="new_password2"]').value;
                    const err = document.getElementById('confErr');
                    if (p1 !== p2) {
                        err.textContent = 'New passwords do not match.';
                        err.classList.add('show');
                        return;
                    }
                    err.classList.remove('show');
                }

                submit();
            });
        }
    });

    // ---------- Password strength ----------
    const newPw = document.getElementById('newPw');
    const bar = document.getElementById('meterBar');
    const label = document.getElementById('meterLabel');

    newPw.addEventListener('input', function () {
        const pw = newPw.value;
        bar.className = 'set-meter-bar';
        label.className = 'set-meter-label';
        label.textContent = '';
        if (!pw) return;

        let score = 0;
        if (pw.length >= 8) score++;
        if (pw.length >= 12) score++;
        if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
        if (/\d/.test(pw)) score++;
        if (/[^A-Za-z0-9]/.test(pw)) score++;

        let cls, text;
        if (score <= 2)      { cls = 'weak';   text = 'Weak password'; }
        else if (score <= 3) { cls = 'fair';   text = 'Fair — could be stronger'; }
        else                 { cls = 'strong'; text = 'Strong password'; }

        bar.classList.add(cls);
        label.classList.add(cls);
        label.textContent = text;
    });

});