/* PabloExchange — fund wallet v2: copy account number + live balance pulse */

document.addEventListener('DOMContentLoaded', function () {

    var btn = document.getElementById('copyAcctBtn');
    if (!btn) return;

    var label = document.getElementById('copyAcctLabel');
    var acct = document.getElementById('acctNum').textContent.trim();

    function fallbackCopy(text, done) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        ta.remove();
        done();
    }

    function done() {
        btn.classList.add('copied');
        label.textContent = 'Copied!';
        setTimeout(function () {
            btn.classList.remove('copied');
            label.textContent = 'Copy account number';
        }, 2000);
    }

    btn.addEventListener('click', function () {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(acct).then(done).catch(function () {
                fallbackCopy(acct, done);
            });
        } else {
            fallbackCopy(acct, done);
        }
    });

});