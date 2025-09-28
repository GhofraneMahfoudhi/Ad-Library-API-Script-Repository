from fb_ads_library_api import FbAdsLibraryTraversal

api = FbAdsLibraryTraversal("medicure.tn", country="TN")
public_url = api.get_public_search_url()
print(f"Public URL: {public_url}\n")

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print("Playwright not installed or import failed:", e)
    raise

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=api.headers.get("User-Agent"))
    page = context.new_page()

    responses = []

    def on_response(response):
        try:
            url = response.url
            status = response.status
            ct = response.headers.get('content-type', '')
            rtype = response.request.resource_type
            snippet = ''
            try:
                if 'json' in ct.lower() or rtype in ('xhr', 'fetch'):
                    text = response.text()
                    snippet = text[:500].replace('\n', ' ')
            except Exception:
                pass
            print(f"RESP: status={status} type={rtype} ct={ct} url={url}")
            if snippet:
                print('  snippet:', snippet[:300])
            responses.append((url, status, ct, rtype, snippet))
        except Exception as e:
            print('response handler error', e)

    page.on('response', on_response)
    page.goto(public_url, timeout=30000)
    try:
        page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        pass

    # Scroll to trigger loads
    for _ in range(5):
        page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
        page.wait_for_timeout(1000)

    page.wait_for_timeout(2000)

    print('\nTotal responses captured:', len(responses))
    browser.close()
