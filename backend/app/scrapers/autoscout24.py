async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list[dict]:
    all_listings = []

    async with self:
        for page_num in range(1, max_pages + 1):
            url = self._build_url(filters, page=page_num)
            logger.info(f"[AutoScout24] Stranica {page_num}: {url}")

            # Ne cekaj specific selektor — ucitaj sta god dodje
            page = await self.get_page(url, wait_for=None)
            if not page:
                break

            # DEBUG: pokazi title i dostupne article/listing elemente
            debug = await page.evaluate("""
                () => {
                    const title = document.title;
                    const articles = document.querySelectorAll('article');
                    const allClasses = Array.from(articles).map(a => a.className).slice(0, 3);
                    
                    // Probaj razlicite selektore
                    const s1 = document.querySelectorAll('article.cldt-summary-full-item').length;
                    const s2 = document.querySelectorAll('[data-testid="listing-item"]').length;
                    const s3 = document.querySelectorAll('[data-guid]').length;
                    const s4 = document.querySelectorAll('.cldt-summary-full-item').length;
                    const s5 = document.querySelectorAll('article').length;
                    
                    return { title, allClasses, s1, s2, s3, s4, s5 };
                }
            """)
            logger.info(f"[AutoScout24] DEBUG: {debug}")

            listings_data = await page.evaluate("""
                () => {
                    const items = document.querySelectorAll('article.cldt-summary-full-item');
                    return Array.from(items).map(item => {
                        const id = item.getAttribute('data-guid') || item.getAttribute('id') || '';
                        const titleEl = item.querySelector('h2');
                        const linkEl = item.querySelector('a.cldt-summary-full-item-main');
                        const priceEl = item.querySelector('[data-type="price_block"] .cldt-price');
                        const details = item.querySelectorAll('.cldt-summary-attributes-item');
                        const detailTexts = Array.from(details).map(d => d.textContent.trim());
                        const images = Array.from(item.querySelectorAll('img[src*="autoscout24"]'))
                            .map(img => img.src).filter(src => src && !src.includes('logo'));
                        const locationEl = item.querySelector('.cldt-summary-seller-contact-country');
                        return {
                            external_id: id,
                            title: titleEl?.textContent?.trim() || '',
                            url: linkEl?.href || '',
                            price_raw: priceEl?.textContent?.trim() || '',
                            details: detailTexts,
                            images: images.slice(0, 10),
                            location_raw: locationEl?.textContent?.trim() || '',
                        };
                    });
                }
            """)

            if not listings_data:
                logger.info(f"[AutoScout24] Nema oglasa na stranici {page_num}")
                await page.close()
                if page_num == 1:
                    break
                continue

            for raw in listings_data:
                parsed = self._parse_listing(raw)
                if parsed:
                    all_listings.append(self.normalize(parsed))

            await page.close()
            await asyncio.sleep(2)
            logger.info(f"[AutoScout24] Skupljeno ukupno: {len(all_listings)}")

    return all_listings
