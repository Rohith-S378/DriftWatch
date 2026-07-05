import scrapy
from datetime import datetime

class ScalerSpider(scrapy.Spider):
    name = "scaler"
    start_urls = [
        "https://www.scaler.com/courses/",
    ]

    def parse(self, response):
        headline = response.css("h1::text").get("").strip()
        subheadlines = response.css("h2::text").getall()
        full_text = " ".join(
            response.css("p::text, li::text, h3::text").getall()
        )
        pricing = " ".join(
            response.css(
                "[class*='price']::text, [class*='fee']::text, [class*='cost']::text"
            ).getall()
        )
        cta = response.css(
            "a.btn::text, button::text, [class*='cta']::text"
        ).getall()

        yield {
            "company": "Scaler",
            "url": response.url,
            "scraped_at": datetime.utcnow().isoformat(),
            "headline": headline,
            "subheadlines": subheadlines[:5],
            "cta_buttons": cta[:8],
            "pricing_text": pricing[:500],
            "full_text": full_text[:3000],
        }
