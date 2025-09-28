#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import json
import re
import time

import requests


def get_ad_archive_id(data):
    """
    Extract ad_archive_id from ad_snapshot_url
    """
    return re.search(r"/\?id=([0-9]+)", data["ad_snapshot_url"]).group(1)


class FbAdsLibraryTraversal:
    # The async endpoint sometimes returns empty pages; construct a public-facing
    # search URL that includes the parameters known to return results in the
    # Ads Library UI. We still keep an async URL pattern for bulk fetching.
    default_url_pattern = (
        "https://www.facebook.com/ads/library/async/search_ads/?q={q}&active_status=all&ad_type=all&country={country}&limit={limit}"
    )

    public_url_pattern = (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&is_targeted_country=false&media_type=all&q={q}&search_type=keyword_unordered"
    )

    def __init__(
        self,
        search_term,
        country="TN",
        page_limit=500,
        retry_limit=3,
    ):
        self.search_term = search_term
        self.country = country
        self.page_limit = page_limit
        self.retry_limit = retry_limit or 3
        # Minimal headers to imitate a real browser; Referer points to the public UI
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

    def generate_ad_archives(self):
        # Start from the async URL (bulk) with named params
        next_page_url = self.default_url_pattern.format(
            q=self.search_term,
            country=self.country,
            limit=self.page_limit,
        )
        return self._get_ad_archives_from_url(next_page_url)

    def get_public_search_url(self):
        """Return the Ads Library public search URL (openable in a browser).

        This uses 'active_status=active' and 'search_type=keyword_unordered' so
        it matches the non-empty UI search the user expects.
        """
        return self.public_url_pattern.format(country=self.country, q=self.search_term)

    def generate_ad_archives_from_public_page(self, max_wait=20):
        """Use a headless browser (Playwright) to load the public Ads Library page
        and capture XHR responses that contain ad data in JSON format.

        This requires `playwright` to be installed. It yields lists of ad_archives
        similar to the async endpoint.
        """
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError(
                "Playwright is required for public-page fetching. Install with: pip install playwright && playwright install"
            )

        public_url = self.get_public_search_url()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.headers.get("User-Agent"))
            page = context.new_page()

            collected = []

            def handle_response(response):
                try:
                    ct = response.headers.get("content-type", "") or ""
                    is_json_ct = "json" in ct.lower()
                    is_xhr = response.request.resource_type in ("xhr", "fetch")
                    if is_json_ct or is_xhr:
                        try:
                            text = response.text()
                            data = json.loads(text)
                            # Accept dicts that contain 'data' or lists of items
                            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                                collected.append(data["data"])
                            elif isinstance(data, list) and len(data) > 0:
                                collected.append(data)
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto(public_url, timeout=max_wait * 1000)

            # Wait for network to be mostly idle
            try:
                page.wait_for_load_state("networkidle", timeout=max_wait * 1000)
            except Exception:
                # networkidle may time out; continue anyway
                pass

            # Scroll a few times to trigger lazy loads / further XHRs
            for _ in range(6):
                try:
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                except Exception:
                    pass
                page.wait_for_timeout(1000)

            # Small extra wait for remaining requests
            page.wait_for_timeout(2000)

            # Yield collected batches
            for batch in collected:
                yield batch

            # If we didn't capture JSON XHRs, attempt a DOM-based fallback to
            # extract ad snapshot links and nearby page names from the rendered
            # HTML. This is a best-effort approach and may need tuning.
            if len(collected) == 0:
                try:
                    dom_items = page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a[href*="/ads/library/"]'));
                        const items = [];
                        anchors.forEach(a => {
                            try {
                                const href = a.href || '';
                                const text = (a.innerText || '').trim();
                                let pageName = text;
                                const parent = a.closest('div');
                                if (parent) {
                                    const nameEl = parent.querySelector('[data-testid], [aria-label], h3, span');
                                    if (nameEl && nameEl.innerText) {
                                        pageName = nameEl.innerText.trim();
                                    }
                                }
                                items.push({page_name: pageName, ad_snapshot_url: href});
                            } catch (e) {}
                        });
                        return items;
                    }""")
                    if dom_items and isinstance(dom_items, list) and len(dom_items) > 0:
                        yield dom_items
                except Exception:
                    pass

            try:
                browser.close()
            except Exception:
                pass

    def _get_ad_archives_from_url(self, next_page_url):
        timeout = 10
        while next_page_url is not None:
            attempt = 0
            response = None
            while attempt < self.retry_limit:
                attempt += 1
                try:
                    # set Referer to the public page to mimic browser navigation
                    headers = dict(self.headers)
                    try:
                        headers["Referer"] = self.public_url_pattern.format(country=self.country, q=self.search_term)
                    except Exception:
                        pass
                    response = requests.get(next_page_url, headers=headers, timeout=timeout)
                except requests.RequestException as e:
                    print(f"Request error (attempt {attempt}) for {next_page_url}: {e}")
                    if attempt < self.retry_limit:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        break

                if response is None:
                    break

                if response.status_code != 200:
                    print(f"HTTP error {response.status_code} for URL {next_page_url} (attempt {attempt})")
                    if attempt < self.retry_limit:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        break

                # Got a 200, try to decode JSON
                try:
                    response_data = json.loads(response.text)
                except json.JSONDecodeError:
                    # If the response is HTML, likely the async endpoint blocked or returned UI
                    text_snippet = response.text[:200].replace('\n', ' ')
                    print(f"Failed to decode JSON from {next_page_url}. Response snippet: {text_snippet}")
                    # Don't retry endlessly on invalid content; break out
                    response_data = None
                    break

                # Vérifie si des données sont présentes
                if not response_data or "data" not in response_data or len(response_data["data"]) == 0:
                    # No data — stop iteration
                    break

                yield response_data["data"]

                # Pagination (si disponible)
                next_page_url = response_data.get("paging", {}).get("next")

    @classmethod
    def generate_ad_archives_from_url(cls, failure_url, after_date="1970-01-01"):
        """
        if we failed from error, later we can just continue from the last failure url
        """
        # _get_ad_archives_from_url only accepts the next_page_url parameter.
        # We yield results from that URL and, if after_date is provided,
        # filter out ad_archives that started before after_date.
        for ad_archives in cls._get_ad_archives_from_url(failure_url):
            if after_date:
                try:
                    from datetime import datetime

                    cutoff = datetime.strptime(after_date, "%Y-%m-%d")
                    def keep(ad):
                        try:
                            ad_date = datetime.strptime(ad.get("ad_delivery_start_time", "1970-01-01"), "%Y-%m-%d")
                            return ad_date >= cutoff
                        except Exception:
                            return False

                    filtered = list(filter(keep, ad_archives))
                except Exception:
                    # If date parsing fails, just yield original batch
                    filtered = ad_archives
                if filtered:
                    yield filtered
            else:
                yield ad_archives
