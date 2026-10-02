"""News layer: structured records (``NewsItem``), scheduled events with no-trade windows,
sentiment impulse. Ingestion (T-005) is owned by news-analyst."""

from news.schema import Category, NewsItem, ScheduledEvent, Tier, sentiment_impulse

__all__ = ["Category", "NewsItem", "ScheduledEvent", "Tier", "sentiment_impulse"]
