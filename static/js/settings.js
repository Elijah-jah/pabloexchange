/* PabloExchange — settings: plain form saves (works with existing JSON view) */

document.addEventListener('DOMContentLoaded', function () {

    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return m ? decodeURIComponent(m[2]) : '';
    }

    document.querySelectorAll('.settings-form').forEach(function (form) {
        const action = form.dataset.action;
        const status = form.querySelector('.form-status');
        const btn = form.querySelector('.btn-save');

        function setStatus(message, isError) {
            status.textContent = message;
            status.className = 'form-status ' + (isError ? 'error' : 'ok');
        }

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            // ---- simple client-side checks ----
            if (action === 'profile') {
                const u = form.querySelector('[name="username"]').value.trim();
                if (!u || u.length < 3) {
                    setStatus('Username must be at least 3 characters.', true);
                    return;
                }
            }

            if (action === 'password') {
                const p1 = form.querySelector('[name="new_password1"]').value;
                const p2 = form.querySelector('[name="new_password2"]').value;
                if (p1 !== p2) {
                    setStatus('New passwords do not match.', true);
                    return;
                }
                if (!form.querySelector('[name="current_password"]').value) {
                    setStatus('Enter your current password.', true);
                    return;
                }
            }

            // ---- submit ----
            btn.disabled = true;
            const original = btn.textContent;
            btn.textContent = 'Saving…';

            fetch('', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                body: new FormData(form),
            })
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (data.ok) {
                        setStatus(data.message || 'Saved.', false);
                        if (action === 'password') form.reset();
                    } else {
                        setStatus(data.error || 'Something went wrong. Try again.', true);
                    }
                })
                .catch(function () {
                    setStatus('Network error — try again.', true);
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.textContent = original;
                });
        });
    });

});