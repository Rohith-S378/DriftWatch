import scrapy
from datetime import datetime

class CourseraSpider(scrapy.Spider):
    name = "coursera"
    start_urls = [
        "https://www.coursera.org/courses?query=programming",
    ]

    def parse(self, response):
        yield {
            "company": "Coursera",
            "url": response.url,
            "scraped_at": datetime.utcnow().isoformat(),
            "headline": response.css("h1::text").get("").strip(),
            "subheadlines": response.css("h2::text").getall()[:5],
            "cta_buttons": response.css("button::text").getall()[:8],
            "pricing_text": " ".join(
                response.css("[class*='price']::text").getall()
            )[:500],
            "full_text": " ".join(
                response.css("p::text, li::text").getall()
            )[:3000],
        }
