from app.scrapers.autoscout24 import AutoScout24Scraper
from app.scrapers.polovni import PolvoniScraper
from app.scrapers.mobile_de import MobileDeScraper
from app.scrapers.willhaben import WillhabenScraper

__all__ = ["AutoScout24Scraper", "PolvoniScraper", "MobileDeScraper", "WillhabenScraper"]

PORTALS = {
    "autoscout24": AutoScout24Scraper,
    "polovni":     PolvoniScraper,
    "mobile_de":   MobileDeScraper,
    "willhaben":   WillhabenScraper,
}
