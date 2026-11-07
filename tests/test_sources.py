import os
import unittest
from unittest import mock

from tests.helpers import NOW, FakeHttp, FIXTURES, fixture
from tgv.sources.base import SourceNotConfigured
from tgv.sources.manual import load_csv
from tgv.sources.reddit import RedditConnector
from tgv.sources.rss import RssConnector
from tgv.sources.youtube import LIST_COST, SEARCH_COST, YouTubeSearchConnector, parse_duration


class RssTest(unittest.TestCase):
    def test_rss_parsing(self):
        items = RssConnector("Example", "https://news.example.com/feed").parse(fixture("press_feed.xml"), NOW)
        self.assertEqual(len(items), 3)  # undated item dropped
        first = items[0]
        self.assertEqual(first.title, "GTA 6 trailer 3 release date announced by Rockstar")
        self.assertEqual(first.published_at.isoformat(), "2026-11-06T18:00:00+00:00")
        self.assertEqual(first.description, "Rockstar Games has announced when the third trailer arrives.")
        self.assertEqual(first.author, "Jane Doe")
        self.assertIsNone(first.metrics)

    def test_youtube_channel_atom_feed(self):
        items = RssConnector("Rockstar", "https://yt", official=True).parse(fixture("youtube_channel_feed.xml"), NOW)
        self.assertEqual(len(items), 1)
        v = items[0]
        self.assertTrue(v.is_official)
        self.assertEqual(v.media_type, "video")
        self.assertEqual(v.external_id, "AAAAAAAAAAA")
        self.assertEqual(v.metrics.views, 25_000_000)
        self.assertEqual(v.metrics.likes, 900_000)


class YouTubeTest(unittest.TestCase):
    def http(self):
        return FakeHttp({
            "https://www.googleapis.com/youtube/v3/search": fixture("youtube_search.json"),
            "https://www.googleapis.com/youtube/v3/videos": fixture("youtube_videos.json"),
        })

    def test_without_key_is_skipped(self):
        with mock.patch.dict(os.environ, {"TGV_YOUTUBE_API_KEY": ""}):
            with self.assertRaises(SourceNotConfigured):
                YouTubeSearchConnector(["GTA 6"]).fetch(self.http(), NOW)

    def test_search_then_statistics(self):
        http = self.http()
        c = YouTubeSearchConnector(["GTA 6"], region_codes=["US"])
        with mock.patch.dict(os.environ, {"TGV_YOUTUBE_API_KEY": "dummy"}):
            items = c.fetch(http, NOW)
        self.assertEqual(len(items), 2)
        long_video, short = items
        self.assertEqual(long_video.media_type, "video")
        self.assertEqual(long_video.duration_seconds, 750)
        self.assertEqual(long_video.language, "en")
        self.assertEqual(long_video.metrics.views, 800_000)
        self.assertEqual(short.media_type, "short")
        self.assertEqual(short.license, "creativeCommon")
        self.assertIsNone(short.metrics.comments)  # not exposed = None, not 0
        self.assertEqual(c.units_spent, SEARCH_COST + LIST_COST)
        search_params = http.calls[0][1]
        self.assertEqual(search_params["publishedAfter"], "2026-11-04T00:00:00Z")
        self.assertEqual(search_params["regionCode"], "US")

    def test_budget_stops_searches(self):
        http = self.http()
        c = YouTubeSearchConnector(["a", "b", "c"], region_codes=["US"])
        c.budget_left = 150  # room for one search + one videos.list
        with mock.patch.dict(os.environ, {"TGV_YOUTUBE_API_KEY": "dummy"}):
            c.fetch(http, NOW)
        searches = [u for u, _ in http.calls if u.endswith("/search")]
        self.assertEqual(len(searches), 1)
        self.assertLessEqual(c.units_spent, 150)

    def test_parse_duration(self):
        self.assertEqual(parse_duration("PT1H2M3S"), 3723)
        self.assertEqual(parse_duration("PT59S"), 59)
        self.assertEqual(parse_duration("P1DT1S"), 86401)
        self.assertIsNone(parse_duration("garbage"))


class RedditTest(unittest.TestCase):
    def test_skipped_without_credentials(self):
        with mock.patch.dict(os.environ, {"TGV_REDDIT_CLIENT_ID": "", "TGV_REDDIT_CLIENT_SECRET": ""}):
            with self.assertRaises(SourceNotConfigured):
                RedditConnector(["GTA6"]).fetch(FakeHttp({}), NOW)

    def test_parses_posts_and_skips_stickied(self):
        http = FakeHttp({"https://oauth.reddit.com/r/GTA6/hot": fixture("reddit_hot.json")})
        with mock.patch.dict(os.environ, {"TGV_REDDIT_CLIENT_ID": "id", "TGV_REDDIT_CLIENT_SECRET": "pw"}):
            items = RedditConnector(["GTA6"]).fetch(http, NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_name, "r/GTA6")
        self.assertIsNone(items[0].metrics.views)
        self.assertEqual(items[0].metrics.comments, 900)


class ManualCsvTest(unittest.TestCase):
    def test_import_with_brazilian_number_format(self):
        items, errors = load_csv(FIXTURES / "manual.csv", NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].metrics.views, 1_200_000)
        self.assertEqual(items[0].country, "US")
        self.assertEqual(items[0].media_type, "short")
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
