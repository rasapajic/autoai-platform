# AutoAI Platform — Dev Notes

## Status: 17.05.2026

### Infrastruktura
- Backend: `autoai-platform-production.up.railway.app`
- Frontend: `content-youth-production-8de0.up.railway.app`
- Cron job: `appealing-communication` — runs 02:00 AM i 02:00 PM UTC
- GitHub: `rasapajic/autoai-platform`
- Railway project: `overflowing-eagerness`

### Fajlovi izmenjeni danas

#### `backend/app/scrapers/autoscout24.py`
- `wait_for=None` umesto `wait_for="domcontentloaded"` — base.py tretira string kao CSS selektor, padalo
- Dodata podrška za `MM.YYYY` format datuma pored `MM/YYYY`
- Čekanje na `article[data-guid]` selector pre JS izvršavanja (React render)
- Debug log za prvi oglas po stranici
- Ethanol/Flexifuel → petrol mapping dodat

#### `backend/app/api/analyze.py`
- `wait_for=None` umesto `wait_for="domcontentloaded"` — isti bug, "Ažuriraj podatke" sada radi
- Ethanol/Flexifuel dodat u FUEL_MAP

#### `backend/scripts/scraper.py`
- Uklonjen `run_polovni()` — portal nije za domaće oglase
- Dodata `run_price_estimation()` — SQL median-based procena cena
- Poziv `run_price_estimation()` u `main()`

#### `frontend/src/app/listing/[id]/page.tsx`
- Linija 212: `missingData = !listing.year || !listing.mileage` → `&&`
- `fullImg` funkcija: regex zamena umesto hardcoded dimenzija — sve slike visoka rezolucija

### Rezultati
- 1114 oglasa dobilo AI price estimation
- "DOBRA KUPOVINA" / "FER CENA" / "VISOKA CENA" badge-ovi rade
- Godište se scrape-uje ispravno iz AutoScout24
- "Ažuriraj podatke sa portala" radi

### Poznati problemi
- Mobile.de blokira scraping ("Zugriff verweigert") — 0 rezultata
- Gorivo "hybrid" za stare Ethanol/FlexiFuel oglase (pre današnjeg fixa)
- Neki oglasi nemaju godište ako su jedinstveni make/model u bazi

### TODO
- [ ] Mobile.de fix ili zamena drugim izvorom
- [ ] Godište filter u pretrazi — testirati
- [ ] Povećati broj stranica po scrape runu kada baza poraste
- [ ] Razmotriti willhaben.at kao dodatni izvor za AT tržište
