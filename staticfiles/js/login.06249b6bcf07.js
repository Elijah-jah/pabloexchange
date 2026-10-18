/* PabloExchange — login page interactions */

document.addEventListener('DOMContentLoaded', function () {

    const form = document.getElementById('loginForm');
    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const submitBtn = document.getElementById('submitBtn');
    const togglePass = document.getElementById('togglePass');
    const toggleIcon = document.getElementById('toggleIcon');

    // ---------- Show / hide password ----------
    togglePass.addEventListener('click', function () {
        const showing = password.type === 'text';
        password.type = showing ? 'password' : 'text';
        toggleIcon.className = showing ? 'bi bi-eye-fill' : 'bi bi-eye-slash-fill';
        togglePass.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
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

    function validEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    // ---------- Live validation ----------
    email.addEventListener('blur', function () {
        const v = email.value.trim();
        if (!v) setError(email, emailError, 'Email is required.');
        else if (!validEmail(v)) setError(email, emailError, 'Please enter a valid email address.');
        else setError(email, emailError, '');
    });

    password.addEventListener('blur', function () {
        if (!password.value) setError(password, passwordError, 'Password is required.');
        else setError(password, passwordError, '');
    });

    // Clear error as the user types
    email.addEventListener('input', () => setError(email, emailError, ''));
    password.addEventListener('input', () => setError(password, passwordError, ''));

    // ---------- Submit ----------
    form.addEventListener('submit', function (e) {
        let ok = true;

        const v = email.value.trim();
        if (!v) { setError(email, emailError, 'Email is required.'); ok = false; }
        else if (!validEmail(v)) { setError(email, emailError, 'Please enter a valid email address.'); ok = false; }

        if (!password.value) { setError(password, passwordError, 'Password is required.'); ok = false; }

        if (!ok) {
            e.preventDefault();
            return;
        }

        // Show spinner, disable double-submit
        submitBtn.disabled = true;
        submitBtn.querySelector('.submit-text').style.display = 'none';
        submitBtn.querySelector('.submit-spinner').style.display = 'inline-flex';
    });

    // ---------- Focus first empty field ----------
    if (!email.value) email.focus();
    else password.focus();

});