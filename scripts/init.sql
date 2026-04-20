-- ============================================================
-- AutoAI Platform - Kompletna šema baze podataka
-- ============================================================

-- Aktiviraj pgvector ekstenziju (za AI embeddings)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- za brži LIKE search

-- ─────────────────────────────────────────────────────────────
-- TABELA: users
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name        VARCHAR(100),
    is_active   BOOLEAN DEFAULT true,
    is_premium  BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: listings (glavna tabela oglasa)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         VARCHAR(200) UNIQUE NOT NULL,
    source              VARCHAR(50) NOT NULL,   -- 'autoscout24', 'polovni', 'mobile_de'

    -- Osnovna vozila
    make                VARCHAR(80),            -- 'BMW', 'Volkswagen'
    model               VARCHAR(120),           -- '5 Series', 'Golf'
    variant             VARCHAR(120),           -- '530d xDrive', 'GTI'
    year                INTEGER,
    
    -- Cena
    price               DECIMAL(10,2),
    currency            VARCHAR(3) DEFAULT 'EUR',
    price_negotiable    BOOLEAN DEFAULT false,
    
    -- Tehničke karakteristike
    mileage             INTEGER,                -- u km
    fuel_type           VARCHAR(30),            -- 'diesel', 'petrol', 'electric', 'hybrid', 'lpg'
    transmission        VARCHAR(30),            -- 'manual', 'automatic'
    engine_cc           INTEGER,                -- zapremina motora u cc
    engine_power_kw     INTEGER,                -- snaga u kW
    body_type           VARCHAR(40),            -- 'sedan', 'suv', 'hatchback', 'kombi', 'coupe'
    color               VARCHAR(50),
    doors               INTEGER,
    seats               INTEGER,
    
    -- Lokacija
    country             VARCHAR(60),            -- 'DE', 'RS', 'AT', 'FR'
    city                VARCHAR(100),
    postal_code         VARCHAR(20),
    latitude            DECIMAL(9,6),
    longitude           DECIMAL(9,6),
    
    -- Stanje i historija
    condition           VARCHAR(30),            -- 'new', 'used', 'damaged'
    first_registration  DATE,
    owners_count        INTEGER,
    service_history     BOOLEAN,
    accident_free       BOOLEAN,
    
    -- Mediji i opis
    description         TEXT,
    images              JSONB DEFAULT '[]',     -- lista URL-ova slika
    features            JSONB DEFAULT '[]',     -- lista opreme: ['Klima', 'Navigacija', ...]
    
    -- Oglas meta
    url                 TEXT NOT NULL,
    dealer_id           UUID,                   -- NULL = privatni oglas
    is_active           BOOLEAN DEFAULT true,
    first_seen_at       TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ DEFAULT NOW(),
    scraped_at          TIMESTAMPTZ DEFAULT NOW(),
    
    -- AI procena cene
    price_estimated     DECIMAL(10,2),          -- model procena
    price_delta_pct     DECIMAL(6,2),           -- % razlika (negativno = povoljno)
    price_rating        VARCHAR(10),            -- 'great', 'good', 'fair', 'high', 'overpriced'
    
    -- AI embedding za semantic search
    embedding           vector(1536)
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: price_history
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    price       DECIMAL(10,2) NOT NULL,
    currency    VARCHAR(3) DEFAULT 'EUR',
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: dealers
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dealers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100),
    source      VARCHAR(50),
    name        VARCHAR(200) NOT NULL,
    country     VARCHAR(60),
    city        VARCHAR(100),
    address     TEXT,
    phone       VARCHAR(50),
    website     TEXT,
    rating      DECIMAL(3,2),
    reviews_count INTEGER DEFAULT 0,
    is_verified BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: user_searches (historija pretraga)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_searches (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id  VARCHAR(100),                   -- za anonimne korisnike
    query_text  TEXT,                           -- originalni prirodni tekst
    filters     JSONB NOT NULL DEFAULT '{}',    -- parsovani filteri
    results_count INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: alerts (obaveštenja o novim oglasima)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(200),
    filters     JSONB NOT NULL DEFAULT '{}',
    is_active   BOOLEAN DEFAULT true,
    frequency   VARCHAR(20) DEFAULT 'daily',    -- 'instant', 'daily', 'weekly'
    last_sent_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: favorites
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS favorites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id  UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, listing_id)
);

-- ─────────────────────────────────────────────────────────────
-- TABELA: scraper_runs (monitoring scrapera)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal          VARCHAR(50) NOT NULL,
    status          VARCHAR(20) DEFAULT 'running',  -- 'running', 'success', 'failed'
    listings_found  INTEGER DEFAULT 0,
    listings_new    INTEGER DEFAULT 0,
    listings_updated INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

-- ─────────────────────────────────────────────────────────────
-- INDEKSI za brže pretrage
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_listings_make         ON listings(make);
CREATE INDEX IF NOT EXISTS idx_listings_make_model   ON listings(make, model);
CREATE INDEX IF NOT EXISTS idx_listings_price        ON listings(price) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_listings_year         ON listings(year) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_listings_mileage      ON listings(mileage) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_listings_country      ON listings(country);
CREATE INDEX IF NOT EXISTS idx_listings_fuel         ON listings(fuel_type);
CREATE INDEX IF NOT EXISTS idx_listings_source       ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_active       ON listings(is_active, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_price_rating ON listings(price_rating) WHERE is_active = true;

-- Trigram indeksi za brži LIKE pretragu
CREATE INDEX IF NOT EXISTS idx_listings_make_trgm  ON listings USING gin(make gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_listings_model_trgm ON listings USING gin(model gin_trgm_ops);

-- Vector indeks za semantic search
CREATE INDEX IF NOT EXISTS idx_listings_embedding
    ON listings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_price_history_listing ON price_history(listing_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user           ON alerts(user_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_favorites_user        ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_searches_user         ON user_searches(user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- TRIGGER: auto-update updated_at
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────
-- TRIGGER: auto-save price history kad se cena promeni
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION track_price_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.price IS DISTINCT FROM NEW.price AND NEW.price IS NOT NULL THEN
        INSERT INTO price_history(listing_id, price, currency)
        VALUES (NEW.id, NEW.price, NEW.currency);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER listings_price_tracker
    AFTER UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION track_price_change();

-- ─────────────────────────────────────────────────────────────
-- Test podaci
-- ─────────────────────────────────────────────────────────────
INSERT INTO listings (
    external_id, source, make, model, year, price, currency,
    mileage, fuel_type, transmission, country, city,
    body_type, engine_power_kw, url, is_active,
    price_estimated, price_delta_pct, price_rating
) VALUES (
    'TEST001', 'manual', 'BMW', '5 Series', 2019, 22500, 'EUR',
    87000, 'diesel', 'automatic', 'DE', 'München',
    'sedan', 140, 'https://example.com/test001', true,
    25000, -10.0, 'great'
), (
    'TEST002', 'manual', 'Volkswagen', 'Golf', 2020, 18900, 'EUR',
    45000, 'petrol', 'manual', 'AT', 'Wien',
    'hatchback', 110, 'https://example.com/test002', true,
    17500, 8.0, 'high'
), (
    'TEST003', 'manual', 'Toyota', 'Corolla', 2021, 21000, 'EUR',
    32000, 'hybrid', 'automatic', 'FR', 'Paris',
    'sedan', 90, 'https://example.com/test003', true,
    21500, -2.3, 'fair'
);

-- Inicijalni price_history za test podatke
INSERT INTO price_history (listing_id, price)
SELECT id, price FROM listings WHERE source = 'manual';
