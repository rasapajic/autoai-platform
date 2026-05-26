def get_scraper(portal: str):
    if portal == "autoscout24":
        from app.scrapers.autoscout24 import AutoScout24Scraper
        return AutoScout24Scraper()
    elif portal == "polovni":
        from app.scrapers.polovni import PolvoniScraper
        return PolvoniScraper()
    elif portal == "mobile_de":
        from app.scrapers.mobile_de import MobileDeScraper
        return MobileDeScraper()
    elif portal == "willhaben":
        from app.scrapers.willhaben import WillhabenScraper
        return WillhabenScraper()
    else:
        raise ValueError(f"Nepoznat portal: {portal}")

PORTALS = ["autoscout24", "polovni", "mobile_de", "willhaben"]
