import time
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from countries.models import Country
from pricing.models import Pricing, PricingConfiguration
from smsmarket.models import Service
from smsmarket.providers import get_provider

NO_STOCK_MSG = "No numbers are currently available"
PROVIDER = 'instantnums'


def _normalize_catalog(raw):
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        for wrapper in ("countries", "services", "data", "result", "items", "list"):
            if isinstance(raw.get(wrapper), (list, dict)):
                return _normalize_catalog(raw[wrapper])
        out = []
        for k, v in raw.items():
            if isinstance(v, dict):
                item = dict(v)
                item.setdefault("ID", k)
                out.append(item)
            elif str(k).lstrip("-").isdigit():
                out.append({"ID": int(k), "name": v})
        return out
    return []


def _iso_for(c):
    for key in ("short_name", "iso", "iso2", "country_code", "code"):
        v = c.get(key)
        if isinstance(v, str) and len(v.strip()) == 2:
            return v.strip().upper()
    return None


def _extract_price(data):
    if not isinstance(data, dict):
        return None, None
    price = data.get("price_usd", data.get("price", data.get("cost")))
    stock = data.get("available", data.get("stock", data.get("count")))
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    try:
        stock = int(stock) if stock is not None else None
    except (TypeError, ValueError):
        stock = None
    return price, stock


class Command(BaseCommand):
    help = ("Sync InstantNums (Server 2) catalog + prices. "
            "Rate limit is 1000 calls/hour — chunk with --countries and --delay.")

    def add_arguments(self, parser):
        parser.add_argument("--countries", default="US",
                            help="Comma-separated ISO codes, e.g. US,GB,DE. 'ALL' = every active country.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Max services per country this run (0 = all). Re-runs update in place.")
        parser.add_argument("--delay", type=float, default=1.0,
                            help="Seconds between API calls. Use ~3.6 to stay under 1000/hour.")
        parser.add_argument("--catalog-only", action="store_true",
                            help="Only sync countries/services lists, skip pricing.")

    def handle(self, *args, **options):
        p = get_provider(PROVIDER)

        # ---------------- Countries + services catalog ----------------
        countries = _normalize_catalog(p.get_countries())
        c_created = c_skipped = 0
        for c in countries:
            iso = _iso_for(c)
            if not iso:
                c_skipped += 1
                continue
            _, created = Country.objects.get_or_create(
                code=iso, defaults={"name": str(c["name"])[:100], "is_active": True})
            c_created += created
        self.stdout.write(f"Countries: {c_created} new, {c_skipped} skipped (virtual/no ISO)")

        services = _normalize_catalog(p.get_services())
        s_created = 0
        for s in services:
            slug = slugify(str(s.get("name", "")))[:50] or str(s.get("ID", "")).lower()
            if not slug:
                continue
            _, created = Service.objects.get_or_create(
                provider=PROVIDER, code=slug,
                defaults={"name": str(s.get("name", slug))[:100], "is_active": True})
            s_created += created
        self.stdout.write(f"Services: {s_created} new "
                          f"({Service.objects.filter(provider=PROVIDER).count()} total for Server 2)")

        if options["catalog_only"]:
            self.stdout.write(self.style.SUCCESS("Catalog sync complete."))
            return

        # ---------------- Pricing ----------------
        config = PricingConfiguration.objects.first()
        if not config:
            self.stdout.write(self.style.ERROR("Create a PricingConfiguration row first (admin)."))
            return

        if options["countries"].upper() == "ALL":
            targets = list(Country.objects.filter(is_active=True))
        else:
            codes = [c.strip().upper() for c in options["countries"].split(",") if c.strip()]
            targets = list(Country.objects.filter(code__in=codes))

        self.stdout.write(f"Pricing sync: {len(targets)} countries, "
                          f"delay {options['delay']}s, limit {options['limit'] or 'none'}")

        for country in targets:
            self._sync_country(p, config, country, options["limit"], options["delay"])

        self.stdout.write(self.style.SUCCESS("Sync complete."))

    def _sync_country(self, p, config, country, limit, delay):
        created = updated = no_stock = failed = 0
        services = Service.objects.filter(provider=PROVIDER, is_active=True).order_by("code")
        if limit:
            services = services[:limit]

        for i, svc in enumerate(services, 1):
            try:
                data = p.get_price(svc.code, country.code)
            except Exception as e:
                if NO_STOCK_MSG in str(e):
                    no_stock += 1
                    Pricing.objects.filter(provider=PROVIDER, service=svc, country=country) \
                                   .update(is_available=False)
                else:
                    failed += 1
                    self.stdout.write(self.style.WARNING(f"  ! {svc.name}/{country.code}: {e}"))
                time.sleep(delay)
                continue

            cost, stock = _extract_price(data)
            if cost is None:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  ! {svc.name}/{country.code}: no price_usd in response"))
                time.sleep(delay)
                continue

            pricing, was_created = Pricing.objects.get_or_create(
                provider=PROVIDER, service=svc, country=country,
                defaults={"cost_usd": cost,
                          "sell_price": config.price_for(cost),
                          "is_available": bool(stock)},
            )
            if was_created:
                created += 1
            else:
                pricing.cost_usd = cost
                pricing.sell_price = config.price_for(cost)
                pricing.is_available = bool(stock) if stock is not None else pricing.is_available
                pricing.save(update_fields=["cost_usd", "sell_price", "is_available"])
                updated += 1

            if i % 50 == 0:
                self.stdout.write(f"  ... {i}/{len(services)}")
            time.sleep(delay)

        self.stdout.write(
            f"  {country.code}: {created} created, {updated} updated, "
            f"{no_stock} out of stock, {failed} failed")