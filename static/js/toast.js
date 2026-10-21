/* PabloExchange — Toast notifications.
   - Auto-shows Django flash messages as toasts on page load.
   - Exposes window.showToast(text, type) for any page script.
   type: 'success' | 'error' | 'info' | 'warning' */

(function () {
    'use strict';

    var ICONS = {
        success: 'bi-check-circle-fill',
        error: 'bi-exclamation-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };

    var container = null;
    var DURATION = 4000;   // ms before auto-dismiss

    function ensureContainer() {
        if (container) { return container; }
        container = document.createElement('div');
        container.id = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        document.body.appendChild(container);
        return container;
    }

    function showToast(text, type) {
        type = ICONS[type] ? type : 'info';
        var box = ensureContainer();

        var toast = document.createElement('div');
        toast.className = 'px-toast px-toast--' + type;
        toast.innerHTML =
            '<i class="bi ' + ICONS[type] + ' px-toast-icon"></i>' +
            '<span class="px-toast-text"></span>' +
            '<button type="button" class="px-toast-close" aria-label="Dismiss">&times;</button>' +
            '<div class="px-toast-bar"></div>';
        toast.querySelector('.px-toast-text').textContent = text;

        var hideTimer = null;

        function dismiss() {
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
            toast.classList.add('px-toast--out');
            setTimeout(function () { toast.remove(); }, 280);
        }

        toast.querySelector('.px-toast-close').addEventListener('click', dismiss);
        toast.addEventListener('mouseenter', function () {
            toast.classList.add('px-toast--paused');
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        });
        toast.addEventListener('mouseleave', function () {
            toast.classList.remove('px-toast--paused');
            hideTimer = setTimeout(dismiss, 1500);
        });

        box.appendChild(toast);
        requestAnimationFrame(function () { toast.classList.add('px-toast--in'); });
        hideTimer = setTimeout(dismiss, DURATION);
        return toast;
    }

    // Global API: showToast('Number reserved!', 'success')
    window.showToast = showToast;

    // Turn Django flash messages into toasts (staggered if several)
    document.addEventListener('DOMContentLoaded', function () {
        var holder = document.getElementById('django-messages');
        if (!holder) { return; }
        var msgs = holder.querySelectorAll('.dj-msg');
        msgs.forEach(function (el, i) {
            setTimeout(function () {
                showToast(el.textContent.trim(), el.dataset.level || 'info');
            }, 180 * i);
        });
        holder.remove();
    });
})();