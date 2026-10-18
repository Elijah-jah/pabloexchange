/* PabloExchange — signup page interactions */

document.addEventListener('DOMContentLoaded', function () {

    const form = document.getElementById('signupForm');
    const username = document.getElementById('username');
    const email = document.getElementById('email');
    const password1 = document.getElementById('password1');
    const password2 = document.getElementById('password2');
    const terms = document.getElementById('terms');
    const submitBtn = document.getElementById('submitBtn');

    const strengthBar = document.getElementById('strengthBar');
    const strengthLabel = document.getElementById('strengthLabel');

    // ---------- Show / hide password (both fields) ----------
    [['togglePass1', 'toggleIcon1', password1], ['togglePass2', 'toggleIcon2', password2]]
        .forEach(([btnId, iconId, input]) => {
            const btn = document.getElementById(btnId);
            const icon = document.getElementById(iconId);
            btn.addEventListener('click', function () {
                const showing = input.type === 'text';
                input.type = showing ? 'password' : 'text';
                icon.className = showing ? 'bi bi-eye-fill' : 'bi bi-eye-slash-fill';
            });
        });

    // ---------- Validation helpers ----------
    function setError(input, errorEl, message) {
        if (message) {
            input.classList.add('invalid');
            errorEl.textContent = message;
            errorEl.classList.add('show');
        } else {
            input.classList.remove('invalid');
            errorEl.textContent = '';
            errorEl.classList.remove('show');
        }
    }

    function errorEl(id) { return document.getElementById(id); }

    function validEmail(v) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
    }

    // ---------- Password strength ----------
    function scorePassword(pw) {
        let score = 0;
        if (pw.length >= 8) score++;
        if (pw.length >= 12) score++;
        if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
        if (/\d/.test(pw)) score++;
        if (/[^A-Za-z0-9]/.test(pw)) score++;
        return score;
    }

    function updateStrength() {
        const pw = password1.value;
        strengthBar.className = 'strength-bar';
        strengthLabel.className = 'strength-label';
        strengthLabel.textContent = '';

        if (!pw) return;

        const s = scorePassword(pw);
        let cls, label;
        if (s <= 2)      { cls = 'weak';   label = 'Weak — add length, numbers & symbols'; }
        else if (s <= 3) { cls = 'fair';   label = 'Fair — could be stronger'; }
        else             { cls = 'strong'; label = 'Strong password'; }

        strengthBar.classList.add(cls);
        strengthLabel.classList.add(cls);
        strengthLabel.textContent = label;
    }

    password1.addEventListener('input', updateStrength);

    // ---------- Live validation ----------
    username.addEventListener('blur', function () {
        const v = username.value.trim();
        if (!v) setError(username, errorEl('usernameError'), 'Username is required.');
        else if (v.length < 3) setError(username, errorEl('usernameError'), 'Username must be at least 3 characters.');
        else setError(username, errorEl('usernameError'), '');
    });

    email.addEventListener('blur', function () {
        const v = email.value.trim();
        if (!v) setError(email, errorEl('emailError'), 'Email is required.');
        else if (!validEmail(v)) setError(email, errorEl('emailError'), 'Please enter a valid email address.');
        else setError(email, errorEl('emailError'), '');
    });

    password2.addEventListener('blur', function () {
        if (password2.value && password2.value !== password1.value) {
            setError(password2, errorEl('password2Error'), 'Passwords do not match.');
        } else if (!password2.value) {
            setError(password2, errorEl('password2Error'), 'Please confirm your password.');
        } else {
            setError(password2, errorEl('password2Error'), '');
        }
    });

    // Clear errors as user types
    [username, email, password1, password2].forEach(inp => {
        inp.addEventListener('input', function () {
            inp.classList.remove('invalid');
            const err = inp.parentElement.parentElement.querySelector('.field-error');
            if (err && !err.classList.contains('show')) return;
            const map = { username: 'usernameError', email: 'emailError', password1: 'password1Error', password2: 'password2Error' };
            const el = errorEl(map[inp.id]);
            if (el && el.id) setError(inp, el, '');
        });
    });

    terms.addEventListener('change', function () {
        setError(terms, errorEl('termsError'), '');
    });

    // ---------- Submit ----------
    form.addEventListener('submit', function (e) {
        let ok = true;

        const u = username.value.trim();
        if (!u || u.length < 3) {
            setError(username, errorEl('usernameError'),
                !u ? 'Username is required.' : 'Username must be at least 3 characters.');
            ok = false;
        }

        const v = email.value.trim();
        if (!v) { setError(email, errorEl('emailError'), 'Email is required.'); ok = false; }
        else if (!validEmail(v)) { setError(email, errorEl('emailError'), 'Please enter a valid email address.'); ok = false; }

        if (!password1.value) { setError(password1, errorEl('password1Error'), 'Password is required.'); ok = false; }
        if (!password2.value) { setError(password2, errorEl('password2Error'), 'Please confirm your password.'); ok = false; }
        else if (password2.value !== password1.value) { setError(password2, errorEl('password2Error'), 'Passwords do not match.'); ok = false; }

        if (!terms.checked) {
            setError(terms, errorEl('termsError'), 'You must agree to the Terms to continue.');
            ok = false;
        }

        if (!ok) {
            e.preventDefault();
            return;
        }

        // Show spinner, disable double-submit
        submitBtn.disabled = true;
        submitBtn.querySelector('.submit-text').style.display = 'none';
        submitBtn.querySelector('.submit-spinner').style.display = 'inline-flex';
    });

});