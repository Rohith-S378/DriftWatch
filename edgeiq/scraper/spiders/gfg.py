import scrapy
from datetime import datetime

class GFGSpider(scrapy.Spider):
    name = "gfg"
    start_urls = [
        "https://www.geeksforgeeks.org/courses/",
    ]

    def parse(self, response):
        headline = response.css("h1::text").get("").strip()
        subheadlines = response.css("h2::text").getall()
        full_text = " ".join(response.css("p::text, li::text").getall())
        pricing = " ".join(
            response.css("[class*='price']::text, [class*='rupee']::text").getall()
        )
        cta = response.css("a.btn::text, button::text").getall()

        yield {
            "company": "GeeksforGeeks",
            "url": response.url,
            "scraped_at": datetime.utcnow().isoformat(),
            "headline": headline,
            "subheadlines": subheadlines[:5],
            "cta_buttons": cta[:8],
            "pricing_text": pricing[:500],
            "full_text": full_text[:3000],
        }
