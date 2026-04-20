import numpy as np
import pandas as pd
import joblib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "models" / "price_model.pkl"
MODEL_PATH.parent.mkdir(exist_ok=True)


class PriceEstimator:
    """
    XGBoost model za procenu fer tržišne cene vozila.

    Ulaz:  make, model, year, mileage, fuel_type,
           transmission, country, engine_cc
    Izlaz: procenjena cena u EUR + confidence
    """

    FEATURES = [
        "make", "model", "year", "mileage",
        "fuel_type", "transmission", "country", "engine_cc",
    ]

    def __init__(self):
        self.pipeline = None
        self.is_trained = False

    # ── Treniranje ────────────────────────────────────────────

    def train(self, df: pd.DataFrame) -> dict:
        """
        Trenira model na istorijskim podacima.
        Pozovi jednom kada imaš dovoljno oglasa u bazi (min. 5000).
        """
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OrdinalEncoder
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_percentage_error
        from xgboost import XGBRegressor

        logger.info(f"Treniranje na {len(df)} oglasa...")

        # Čišćenje podataka
        df = df.dropna(subset=self.FEATURES + ["price"])
        df = df[df["price"].between(500, 300_000)]
        df = df[df["mileage"].between(0, 600_000)]
        df = df[df["year"].between(1990, 2025)]

        logger.info(f"Posle čišćenja: {len(df)} oglasa")

        X = df[self.FEATURES].copy()
        y = np.log1p(df["price"])  # log transform za stabilnost

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.pipeline = Pipeline([
            ("encoder", OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
            )),
            ("model", XGBRegressor(
                n_estimators=500,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=5,
                random_state=42,
                n_jobs=-1,
            )),
        ])

        self.pipeline.fit(X_train, y_train)
        self.is_trained = True

        # Evaluacija
        preds = np.expm1(self.pipeline.predict(X_test))
        actuals = np.expm1(y_test)
        mape = mean_absolute_percentage_error(actuals, preds) * 100

        logger.info(f"✅ Model istreniran. MAPE: {mape:.1f}%")

        # Sačuvaj model
        self.save()

        return {
            "samples_trained": len(X_train),
            "mape_percent":    round(mape, 2),
            "model_path":      str(MODEL_PATH),
        }

    # ── Predikcija ────────────────────────────────────────────

    def predict(self, vehicle: dict) -> dict:
        """
        Proceni cenu jednog vozila.

        vehicle = {
            "make": "BMW", "model": "5 Series",
            "year": 2018, "mileage": 95000,
            "fuel_type": "diesel", "transmission": "automatic",
            "country": "DE", "engine_cc": 1998
        }
        """
        if not self.is_trained:
            raise RuntimeError("Model nije istreniran. Pozovi train() ili load().")

        X = pd.DataFrame([{
            "make":         vehicle.get("make", ""),
            "model":        vehicle.get("model", ""),
            "year":         vehicle.get("year", 2015),
            "mileage":      vehicle.get("mileage", 100000),
            "fuel_type":    vehicle.get("fuel_type", ""),
            "transmission": vehicle.get("transmission", ""),
            "country":      vehicle.get("country", ""),
            "engine_cc":    vehicle.get("engine_cc", 0) or 0,
        }])

        log_price = self.pipeline.predict(X)[0]
        estimated = round(np.expm1(log_price), -2)  # zaokruži na 100

        # Confidence na osnovu dostupnih podataka
        filled = sum(1 for k in self.FEATURES if vehicle.get(k))
        confidence = "high" if filled >= 6 else "medium" if filled >= 4 else "low"

        return {
            "estimated_price": float(estimated),
            "confidence":      confidence,
        }

    def predict_batch(self, vehicles: list[dict]) -> list[dict]:
        """Batch predikcija za više vozila odjednom (brže)."""
        if not vehicles:
            return []

        rows = [{
            "make":         v.get("make", ""),
            "model":        v.get("model", ""),
            "year":         v.get("year", 2015),
            "mileage":      v.get("mileage", 100000),
            "fuel_type":    v.get("fuel_type", ""),
            "transmission": v.get("transmission", ""),
            "country":      v.get("country", ""),
            "engine_cc":    v.get("engine_cc", 0) or 0,
        } for v in vehicles]

        X = pd.DataFrame(rows)
        log_prices = self.pipeline.predict(X)
        estimated = np.expm1(log_prices)

        return [
            {"estimated_price": round(float(p), -2), "confidence": "medium"}
            for p in estimated
        ]

    # ── Čuvanje i učitavanje ──────────────────────────────────

    def save(self):
        joblib.dump(self.pipeline, MODEL_PATH)
        logger.info(f"Model sačuvan: {MODEL_PATH}")

    @classmethod
    def load(cls) -> "PriceEstimator":
        """Učitaj sačuvani model. Ako ne postoji — vrati dummy."""
        estimator = cls()
        if MODEL_PATH.exists():
            estimator.pipeline = joblib.load(MODEL_PATH)
            estimator.is_trained = True
            logger.info("✅ Model učitan")
        else:
            logger.warning("⚠️ Model nije pronađen. Koristi train() da istreniraš.")
        return estimator


# ── Skripta za treniranje iz baze ─────────────────────────────

def train_from_database():
    """
    Pokreni ovu funkciju jednom kada imaš dovoljno podataka:
        python -c "from app.ai.price_estimator import train_from_database; train_from_database()"
    """
    from app.core.db import SessionLocal
    from app.models import Listing

    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(
            Listing.price != None,
            Listing.year != None,
            Listing.mileage != None,
            Listing.is_active == True,
        ).all()

        if len(listings) < 500:
            print(f"⚠️ Samo {len(listings)} oglasa. Preporučujemo min. 5000.")

        df = pd.DataFrame([{
            "make":         l.make or "",
            "model":        l.model or "",
            "year":         l.year or 0,
            "mileage":      l.mileage or 0,
            "fuel_type":    l.fuel_type or "",
            "transmission": l.transmission or "",
            "country":      l.country or "",
            "engine_cc":    l.engine_cc or 0,
            "price":        float(l.price),
        } for l in listings])

        estimator = PriceEstimator()
        result = estimator.train(df)
        print(f"✅ Gotovo! {result}")

    finally:
        db.close()
