import anthropic
import logging
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.models import Listing

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class SemanticSearch:
    """
    Semantička pretraga koristeći Claude embeddings + pgvector.

    Npr: "udoban porodični auto za duža putovanja" pronalazi
    kombi/SUV sa dobrim recenzijama za udobnost, čak i ako
    korisnik nije upisao konkretnu marku/model.
    """

    EMBEDDING_MODEL = "voyage-2"  # Anthropic/Voyage embedding model

    def get_embedding(self, text: str) -> list[float]:
        """Generiši embedding vektor za tekst."""
        try:
            # Koristimo OpenAI text-embedding-3-small kao alternativu
            # jer je jeftiniji i brži za embeddings
            from openai import OpenAI
            openai_client = OpenAI()

            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                dimensions=1536,
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding greška: {e}")
            return []

    def embed_listing(self, listing: Listing) -> list[float] | None:
        """Napravi embedding za oglas kombinujući ključne informacije."""
        parts = []

        if listing.make:
            parts.append(listing.make)
        if listing.model:
            parts.append(listing.model)
        if listing.variant:
            parts.append(listing.variant)
        if listing.year:
            parts.append(str(listing.year))
        if listing.fuel_type:
            fuel_map = {
                "diesel": "dizel diesel", "petrol": "benzin petrol",
                "electric": "elektricni electric", "hybrid": "hibrid hybrid",
            }
            parts.append(fuel_map.get(listing.fuel_type, listing.fuel_type))
        if listing.body_type:
            parts.append(listing.body_type)
        if listing.transmission:
            parts.append("automatik" if listing.transmission == "automatic" else "manuelni")
        if listing.features:
            # Dodaj prvih 10 opreme
            parts.extend(listing.features[:10])
        if listing.description:
            # Prvih 200 karaktera opisa
            parts.append(listing.description[:200])

        text = " ".join(parts)
        return self.get_embedding(text)

    def semantic_search(
        self,
        query: str,
        db: Session,
        limit: int = 20,
        filters: dict = None,
    ) -> list[dict]:
        """
        Pretraži oglase semantički — po značenju, ne samo ključnim rečima.

        query = "udoban porodični auto za duža putovanja sa ekonomičnim motorom"
        """
        # Generiši embedding za upit
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []

        # Dodatni filteri u SQL
        where_clauses = ["is_active = true", "embedding IS NOT NULL"]
        params = {
            "embedding": query_embedding,
            "limit": limit,
        }

        if filters:
            if filters.get("max_price"):
                where_clauses.append("price <= :max_price")
                params["max_price"] = filters["max_price"]
            if filters.get("min_year"):
                where_clauses.append("year >= :min_year")
                params["min_year"] = filters["min_year"]
            if filters.get("fuel_type"):
                where_clauses.append("fuel_type = :fuel_type")
                params["fuel_type"] = filters["fuel_type"]
            if filters.get("country"):
                where_clauses.append("country = :country")
                params["country"] = filters["country"]

        where_sql = " AND ".join(where_clauses)

        # pgvector cosine similarity pretraga
        sql = text(f"""
            SELECT
                id, make, model, year, price, mileage,
                fuel_type, country, images, price_rating,
                price_delta_pct, url,
                1 - (embedding <=> :embedding::vector) AS similarity
            FROM listings
            WHERE {where_sql}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id":             str(r.id),
                "make":           r.make,
                "model":          r.model,
                "year":           r.year,
                "price":          float(r.price) if r.price else None,
                "mileage":        r.mileage,
                "fuel_type":      r.fuel_type,
                "country":        r.country,
                "images":         (r.images or [])[:1],
                "price_rating":   r.price_rating,
                "price_delta_pct": float(r.price_delta_pct) if r.price_delta_pct else None,
                "url":            r.url,
                "similarity":     round(float(r.similarity), 3),
            }
            for r in rows
        ]

    def index_listing(self, listing: Listing, db: Session) -> bool:
        """Dodaj/ažuriraj embedding za jedan oglas."""
        embedding = self.embed_listing(listing)
        if not embedding:
            return False

        listing.embedding = embedding
        db.commit()
        return True

    def index_all_unindexed(self, db: Session, batch_size: int = 50) -> int:
        """Indeksiraj sve oglase koji nemaju embedding."""
        listings = db.query(Listing).filter(
            Listing.embedding == None,
            Listing.is_active == True,
        ).limit(batch_size).all()

        count = 0
        for listing in listings:
            if self.index_listing(listing, db):
                count += 1

        logger.info(f"Indeksirano {count} oglasa")
        return count
