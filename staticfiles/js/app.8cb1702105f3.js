/* PabloExchange — app shell behaviour */

document.addEventListener('DOMContentLoaded', function () {

    // ---------- Active nav link based on current path ----------
    const path = window.location.pathname;
    const map = {
        '/dashboard/': 'dashboard',
        '/marketplace/': 'marketplace',
        '/purchases/': 'purchases',
        '/transactions/': 'transactions',
        '/settings/': 'settings',
    };
    const current = map[path];
    if (current) {
        document.querySelectorAll('.px-navbar .nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.nav === current);
        });
    }

    // ---------- Auto-dismiss alerts after 5 seconds ----------
    document.querySelectorAll('.app-alert').forEach(alert => {
        setTimeout(() => {
            if (window.bootstrap) {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            } else {
                alert.style.display = 'none';
            }
        }, 5000);
    });

});

/* ---------- Shared: copy text to clipboard (used across pages) ---------- */
function pxCopy(text, btn) {
    const done = () => {
        if (!btn) return;
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check-lg"></i> Copied';
        btn.classList.add('copied');
        setTimeout(() => { btn.innerHTML = original; btn.classList.remove('copied'); }, 2000);
    };
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
    } else {
        fallbackCopy(text, done);
    }
}

function fallbackCopy(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    ta.remove();
    done();
}