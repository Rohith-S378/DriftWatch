# Scrapy settings for edgescraper project
BOT_NAME = 'edgescraper'
SPIDER_MODULES = ['edgescraper.spiders']
NEWSPIDER_MODULE = 'edgescraper.spiders'

ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 1
HTTPCACHE_ENABLED = True
LOG_LEVEL = 'ERROR'

DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}
