# Global fetcher instance - shared across all requests
from app.services.bist_fetcher import BISTFetcher

# Singleton instance for background fetching
fetcher = BISTFetcher()
