from __future__ import annotations

from abc import ABC, abstractmethod


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        raise NotImplementedError
