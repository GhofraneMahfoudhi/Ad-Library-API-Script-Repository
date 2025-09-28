from fb_ads_library_api import FbAdsLibraryTraversal

api = FbAdsLibraryTraversal("medicure.tn", country="TN")

print("Using public fetch...\n")
try:
    gen = api.generate_ad_archives_from_public_page()
    total = 0
    batches = 0
    for batch in gen:
        batches += 1
        print(f"Batch {batches}: {len(batch)} items")
        total += len(batch)
    print(f"Total items collected: {total}")
except Exception as e:
    print(f"Error during fetch: {e}")
