/* PabloExchange — transactions: type filter + search */

document.addEventListener('DOMContentLoaded', function () {

    const filterBtns = document.querySelectorAll('.tx-filter');
    const search = document.getElementById('txSearch');
    const rows = document.querySelectorAll('.tx-row');
    const noResults = document.getElementById('txNoResults');

    let activeFilter = 'all';

    function apply() {
        const q = search.value.trim().toLowerCase();
        let visible = 0;

        rows.forEach(row => {
            const typeOk = activeFilter === 'all' || row.dataset.type === activeFilter;
            const searchOk = !q || row.dataset.search.includes(q);
            const show = typeOk && searchOk;
            row.style.display = show ? '' : 'none';
            if (show) visible++;
        });

        noResults.style.display = visible === 0 ? 'block' : 'none';
    }

    filterBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeFilter = this.dataset.filter;
            apply();
        });
    });

    search.addEventListener('input', apply);

});