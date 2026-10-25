"""Adapter pool and application service for messaging workflows."""

from __future__ import annotations

from pathlib import Path

from .models import Platform
from .playwright_adapter import BrowserManager, PlaywrightMessagingAdapter
from .workflow import MessagingService


class AdapterPool:
    def __init__(self, profile_root: Path | None = None) -> None:
        self.browser = BrowserManager(profile_root)
        self._adapters: dict[Platform, PlaywrightMessagingAdapter] = {}

    def __call__(self, platform: Platform) -> PlaywrightMessagingAdapter:
        if platform not in self._adapters:
            self._adapters[platform] = PlaywrightMessagingAdapter(platform, self.browser)
        return self._adapters[platform]

    def close(self) -> None:
        self.browser.close()


def create_messaging_service(profile_root: Path | None = None) -> tuple[MessagingService, AdapterPool]:
    adapters = AdapterPool(profile_root)
    return MessagingService(adapters), adapters
