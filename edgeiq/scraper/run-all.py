# scraper/run_all.py
# Run this ONE file to scrape all 4 companies

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import scaler
import gfg
import coursera
import udemy

def main():
    print("\n" + "🚀 " * 20)
    print("  EDGEIQ — RUNNING ALL SCRAPERS")
    print("🚀 " * 20)

    scrapers = [
        ("Scaler",          scaler.run),
        ("GeeksforGeeks",   gfg.run),
        ("Coursera",        coursera.run),
        ("Udemy",           udemy.run),
    ]

    results = []
    for name, run_fn in scrapers:
        try:
            run_fn()
            results.append((name, "✅ Success"))
        except Exception as e:
            results.append((name, f"❌ Failed: {e}"))

    # Summary
    print("\n" + "="*50)
    print("  SCRAPING SUMMARY")
    print("="*50)
    for name, status in results:
        print(f"  {status}  {name}")
    print("="*50)
    print("\n👉 Now run: python ingest_data.py")

if __name__ == "__main__":
    main()