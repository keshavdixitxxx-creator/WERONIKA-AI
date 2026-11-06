import unittest

from weronika_agent.site_registry import (
    REFUSED_DOMAINS,
    SITES,
    find_site,
    refusal_for,
    resolve_target,
    search_sites,
    site_catalog,
)
from weronika_agent.site_service import SiteError, SiteService
from weronika_agent.tasks import TaskError


class FakeBrowser:
    """Stands in for the managed Chromium window."""

    def __init__(self) -> None:
        self.tabs = []
        self.seq = 0
        self.activated = []

    def open_workspace_urls(self, urls):
        opened = []
        for url in urls:
            self.seq += 1
            tab_id = f"t{self.seq}"
            self.tabs.append({"id": tab_id, "url": url, "title": url})
            opened.append({"id": tab_id, "url": url, "status": "opened"})
        return opened

    def workspace_tabs(self):
        return list(self.tabs)

    def close_workspace_tab(self, tab_id):
        before = len(self.tabs)
        self.tabs = [tab for tab in self.tabs if tab["id"] != tab_id]
        return len(self.tabs) < before

    def activate_workspace_tab(self, tab_id):
        if any(tab["id"] == tab_id for tab in self.tabs):
            self.activated.append(tab_id)
            return True
        return False


class RegistryTests(unittest.TestCase):
    def test_catalog_is_large_and_categorised(self):
        catalog = site_catalog()
        self.assertGreaterEqual(catalog["count"], 80)
        self.assertEqual(catalog["count"], len(SITES))
        self.assertIn("google", catalog["categories"])
        self.assertGreaterEqual(len(catalog["categories"]["google"]), 10)
        self.assertTrue(catalog["refused"])

    def test_no_duplicate_ids_or_urls(self):
        ids = [site.id for site in SITES]
        self.assertEqual(len(ids), len(set(ids)))
        urls = [site.url for site in SITES]
        self.assertEqual(len(urls), len(set(urls)))

    def test_spoken_names_resolve(self):
        cases = {
            "open radio garden": "https://radio.garden/",
            "radio garden": "https://radio.garden/",
            "google drive": "https://drive.google.com/",
            "open drive": "https://drive.google.com/",
            "gmail": "https://mail.google.com/",
            "open google docs": "https://docs.google.com/",
            "stopncii": "https://stopncii.org/",
            "cybercrime": "https://cybercrime.gov.in/",
        }
        for text, expected in cases.items():
            url, site = resolve_target(text)
            self.assertEqual(url, expected, text)
            self.assertIsNotNone(site, text)

    def test_plain_addresses_still_open(self):
        url, site = resolve_target("https://example.com/page")
        self.assertEqual(url, "https://example.com/page")
        self.assertIsNone(site)
        url, _ = resolve_target("example.org")
        self.assertEqual(url, "https://example.org")

    def test_unknown_name_is_reported_not_guessed(self):
        with self.assertRaises(TaskError):
            resolve_target("a thing that is not a site")

    def test_refused_destinations_state_a_reason(self):
        for name, _reason in REFUSED_DOMAINS:
            reason = refusal_for(name)
            self.assertIn("will not automate", reason, name)
        for text in ("open vegamovies", "dehashed", "open pimeyes", "callbomber"):
            with self.assertRaises(TaskError) as caught:
                resolve_target(text)
            self.assertIn("will not automate", str(caught.exception))

    def test_refused_list_never_overlaps_the_catalog(self):
        refused = {name.casefold() for name, _ in REFUSED_DOMAINS}
        for site in SITES:
            for alias in (site.id, site.name, *site.aliases):
                self.assertNotIn(alias.casefold(), refused, site.id)

    def test_search_ranks_prefix_matches_first(self):
        results = search_sites("google drive")
        self.assertTrue(results)
        self.assertEqual(results[0]["name"], "Google Drive")
        self.assertEqual(search_sites(""), [])

    def test_find_site_extends_to_longer_phrases(self):
        self.assertIsNotNone(find_site("google drive files"))
        self.assertIsNone(find_site("zzz not a site zzz"))


class SiteServiceTests(unittest.TestCase):
    def build(self):
        browser = FakeBrowser()
        return SiteService(browser), browser

    def test_open_creates_tabs_and_reports_names(self):
        service, browser = self.build()
        result = service.open(["radio garden", "google drive"])
        self.assertEqual(result["count"], 2)
        self.assertIn("Radio Garden", result["message"])
        self.assertEqual(len(browser.tabs), 2)

    def test_open_refuses_before_touching_the_browser(self):
        service, browser = self.build()
        with self.assertRaises(SiteError):
            service.open("vegamovies")
        self.assertEqual(browser.tabs, [])

    def test_open_rejects_an_empty_or_huge_list(self):
        service, _ = self.build()
        with self.assertRaises(SiteError):
            service.open([])
        with self.assertRaises(SiteError):
            service.open([f"site{i}.com" for i in range(11)])

    def test_close_by_name_matches_the_host(self):
        service, browser = self.build()
        service.open(["radio garden", "github"])
        result = service.close(name="radio garden")
        self.assertEqual(result["count"], 1)
        self.assertEqual([tab["url"] for tab in browser.tabs], ["https://github.com/"])

    def test_close_unknown_name_is_reported(self):
        service, _ = self.build()
        with self.assertRaises(SiteError):
            service.close(name="radio garden")

    def test_focus_brings_the_tab_forward(self):
        service, browser = self.build()
        opened = service.open(["youtube"])["opened"]
        service.focus(tab_id=opened[0]["id"])
        self.assertEqual(browser.activated, [opened[0]["id"]])

    def test_focus_missing_tab_is_reported(self):
        service, _ = self.build()
        with self.assertRaises(SiteError):
            service.focus(tab_id="nope")

    def test_catalog_includes_live_tabs(self):
        service, _ = self.build()
        service.open(["wikipedia"])
        catalog = service.catalog()
        self.assertEqual(len(catalog["tabs"]), 1)
        self.assertIn("refused", catalog)

    def test_resolve_describes_without_opening(self):
        service, browser = self.build()
        info = service.resolve("open google maps")
        self.assertTrue(info["known"])
        self.assertEqual(info["url"], "https://www.google.com/maps")
        self.assertEqual(browser.tabs, [])

    def test_broken_browser_surfaces_a_usable_message(self):
        class Broken:
            def open_workspace_urls(self, urls):
                raise RuntimeError("no browser")

            def workspace_tabs(self):
                raise RuntimeError("no browser")

        service = SiteService(Broken())
        with self.assertRaises(SiteError) as caught:
            service.open("youtube")
        self.assertIn("managed browser", str(caught.exception))
        self.assertEqual(service.tabs(), [])


if __name__ == "__main__":
    unittest.main()
