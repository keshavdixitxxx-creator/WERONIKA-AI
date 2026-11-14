import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace

from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.news import NewsError, feed_url, fetch_news, parse_feed
from weronika_agent.workflow import MessagingService
from weronika_agent.workspace import LocalWorkspace

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Top stories - Google News</title>
<item><title>India wins the series &amp; the trophy - The Hindu</title>
<link>https://news.google.com/rss/articles/abc</link>
<pubDate>Fri, 13 Nov 2026 08:00:00 GMT</pubDate>
<description>&lt;a href="https://x.example"&gt;India wins&lt;/a&gt;</description>
<source url="https://www.thehindu.com">The Hindu</source></item>
<item><title><![CDATA[Monsoon <b>arrives</b> early - NDTV]]></title>
<link>http://insecure.example/story</link>
<source url="https://www.ndtv.com">NDTV</source></item>
<item><title>India wins the series &amp; the trophy - The Hindu</title>
<source url="https://www.thehindu.com">The Hindu</source></item>
<item><title></title></item>
<item><title>Markets close higher</title></item>
</channel></rss>"""


class FeedTests(unittest.TestCase):
    def test_headlines_are_plain_text_without_the_source_suffix(self):
        headlines = parse_feed(FEED)
        self.assertEqual(
            [entry["title"] for entry in headlines],
            ["India wins the series & the trophy", "Monsoon arrives early", "Markets close higher"],
        )
        self.assertEqual(headlines[0]["source"], "The Hindu")
        self.assertEqual(headlines[0]["link"], "https://news.google.com/rss/articles/abc")
        self.assertEqual(headlines[0]["published"], "Fri, 13 Nov 2026 08:00:00 GMT")
        self.assertEqual(headlines[1]["link"], "")  # only https links are passed on
        self.assertEqual(headlines[2]["source"], "")

    def test_limit_and_rubbish(self):
        self.assertEqual(len(parse_feed(FEED, 2)), 2)
        self.assertEqual(parse_feed(""), [])
        self.assertEqual(parse_feed("<html><body>Sign in</body></html>"), [])
        self.assertEqual(parse_feed(None), [])

    def test_feed_address(self):
        self.assertEqual(feed_url(), "https://news.google.com/rss?hl=en&gl=IN&ceid=IN:en")
        self.assertEqual(
            feed_url("cricket world cup", "en-IN", "IN"),
            "https://news.google.com/rss/search?q=cricket+world+cup&hl=en-IN&gl=IN&ceid=IN:en",
        )
        self.assertEqual(feed_url("", "hi", "IN"), "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi")

    def test_the_topic_cannot_change_the_address(self):
        url = feed_url("a&gl=XX#frag /../x", "en&x=1", "I N")
        self.assertTrue(url.startswith("https://news.google.com/rss/search?q=a%26gl%3DXX%23frag+%2F..%2Fx&"))
        self.assertTrue(url.endswith("&hl=en&gl=IN&ceid=IN:en"))
        self.assertLessEqual(len(feed_url("x" * 500)), 200)

    def test_fetch_news(self):
        asked = []
        result = fetch_news("cricket", "en-IN", "IN", download=lambda url: asked.append(url) or FEED)
        self.assertEqual(result["topic"], "cricket")
        self.assertEqual(result["source"], "Google News")
        self.assertEqual(len(result["headlines"]), 3)
        self.assertIn("q=cricket", asked[0])

    def test_failures_are_reported(self):
        def offline(url):
            raise urllib.error.URLError("offline")

        with self.assertRaises(NewsError) as raised:
            fetch_news(download=offline)
        self.assertIn("could not reach", str(raised.exception))
        with self.assertRaises(NewsError) as raised:
            fetch_news("cricket", download=lambda url: "<rss></rss>")
        self.assertIn("cricket", str(raised.exception))


class NewsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.asked = []
        self.fail = False

        def news(topic, lang, country):
            self.asked.append((topic, lang, country))
            if self.fail:
                raise NewsError("Weronika could not reach the news feed.")
            return {"topic": topic, "source": "Google News", "headlines": parse_feed(FEED)}

        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                MessagingService(lambda _: None),
                SimpleNamespace(browser=None),
                LocalWorkspace(self.temp.name),
                news=news,
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_headlines(self):
        with urllib.request.urlopen(f"{self.base}/api/news?topic=cricket&lang=en-IN&country=IN", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(self.asked, [("cricket", "en-IN", "IN")])
        self.assertEqual(data["headlines"][0]["title"], "India wins the series & the trophy")

    def test_defaults(self):
        with urllib.request.urlopen(f"{self.base}/api/news", timeout=5):
            pass
        self.assertEqual(self.asked, [("", "en", "IN")])

    def test_a_failed_fetch_is_an_error_not_an_empty_list(self):
        self.fail = True
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(f"{self.base}/api/news", timeout=5)
        self.assertEqual(raised.exception.code, 502)
        self.assertIn("could not reach", json.loads(raised.exception.read().decode("utf-8"))["error"])


if __name__ == "__main__":
    unittest.main()
