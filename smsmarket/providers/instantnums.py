import logging
import time

import requests

from django.conf import settings

from .base import BaseProvider

logger = logging.getLogger(__name__)


class InstantNumsProvider(BaseProvider):
    """InstantNums — global provider, 150+ countries."""

    name = "instantnums"

    # Statuses that simply mean "no SMS yet" — normal state, not an error
    WAITING_STATUSES = ("waiting", "pending", "in_progress", None)

    # Retry config — rides through brief network drops
    MAX_RETRIES = 3
    RETRY_WAIT = 10      # seconds between retries
    RETRYABLE = (requests.Timeout, requests.ConnectionError)

    def __init__(self):
        self.base_url = settings.INSTANTNUMS_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.INSTANTNUMS_API_KEY}",
            "Accept": "application/json",
        }

    def _make_request(self, method, endpoint, **kwargs):
        """Centralized request handler: retries timeouts/connection drops,
        surfaces the provider's error messages, logs everything."""
        url = f"{self.base_url}{endpoint}"
        timeout = kwargs.pop("timeout", 25)

        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    timeout=timeout,
                    **kwargs,
                )
                response.raise_for_status()
                return response.json()

            except self.RETRYABLE as e:
                last_exc = e
                logger.warning(
                    "InstantNums %s %s attempt %d/%d failed: %s",
                    method, url, attempt, self.MAX_RETRIES, e,
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_WAIT)

            except requests.HTTPError as e:
                # Definitive server response — do NOT retry
                try:
                    err_json = e.response.json()
                    detail = err_json.get("message") or err_json.get("error")
                except (ValueError, AttributeError):
                    detail = None
                msg = detail or "Provider returned an error. Please try again."
                logger.error(
                    "InstantNums HTTP error: %s %s - Status: %s - %s",
                    method, url, e.response.status_code, msg,
                )
                raise Exception(msg)

            except requests.RequestException as e:
                last_exc = e
                logger.exception("InstantNums request failed: %s %s", method, url)

        # all retries exhausted
        raise Exception(f"Provider unreachable after {self.MAX_RETRIES} attempts. Check your internet connection.")

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def get_balance(self):
        return self._make_request("GET", "/balance")

    def get_countries(self):
        return self._make_request("GET", "/countries")

    def get_services(self, country=None):
        params = {"country": country} if country else None
        return self._make_request("GET", "/services", params=params)

    def get_price(self, service, country):
        data = self._make_request(
            "GET",
            "/price",
            params={"service": service, "country": country},
        )
        if not data.get("success"):
            logger.error("InstantNums price fetch failed: %s", data)
            raise Exception(data.get("message") or data.get("error") or "Unable to fetch price from InstantNums.")
        return data

    def check_stock(self, service, country):
        data = self._make_request(
            "GET",
            "/stock",
            params={"service": service, "country": country},
        )
        if not data.get("success"):
            logger.error("InstantNums stock check failed: %s", data)
            raise Exception(data.get("message") or data.get("error") or "Unable to check stock from InstantNums.")
        return data

    def purchase(self, service, country):
        data = self._make_request(
            "POST",
            "/sms/purchase",
            json={
                "service": str(service),
                "country": str(country),
            },
        )
        if not data.get("success"):
            logger.error("InstantNums purchase failed: %s", data)
            raise Exception(data.get("message") or data.get("error") or "Unable to purchase a number from InstantNums.")
        return data

    def check_sms(self, order_id):
        data = self._make_request("GET", f"/sms/{order_id}")

        # Normalize the API response to the shape views expect:
        # {"status": "finished", "sms": "12345", "full_sms": "..."}
        # or {"status": "waiting"} while no SMS has arrived.
        code = data.get("code") or data.get("sms_code") or data.get("otp")
        if code:
            return {
                "status": "finished",
                "sms": str(code),
                "full_sms": data.get("full_sms") or data.get("text") or data.get("sms") or "",
            }
        return {"status": "waiting", "sms": "", "full_sms": ""}

    def cancel(self, order_id):
        data = self._make_request("POST", f"/sms/{order_id}/cancel")
        if not data.get("success"):
            logger.error("InstantNums cancel failed for order %s: %s", order_id, data)
            raise Exception(data.get("message") or data.get("error") or "Unable to cancel order from InstantNums.")
        return data