import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from tests.helpers import NOW, FakeHttp, fixture
from tgv import dashboard, db, pipeline
from tgv.cli import main as cli_main
from tgv.sources.rss import RssConnector
from tgv.sources.youtube import YouTubeSearchConnector

CONFIG = {
    "analysis": {"window_days": 7, "cluster_threshold": 0.5, "cluster_window_hours": 72, "min_score_to_select": 1},
    "scoring": {},
}


def connectors():
    yt = YouTubeSearchConnector(["GTA 6"], region_codes=["US"])
    yt.daily_budget = 1000
    return [
        RssConnector("Outlet A", "https://a.example/feed"),
        RssConnector("Outlet B", "https://b.example/feed"),
        RssConnector("Rockstar Games", "https://yt.example/feed", official=True),
        RssConnector("Broken", "https://broken.example/feed"),
        yt,
    ]


def http():
    return FakeHttp({
        "https://a.example/feed": fixture("press_feed.xml"),
        "https://b.example/feed": fixture("press_feed_2.xml"),
        "https://yt.example/feed": fixture("youtube_channel_feed.xml"),
        "https://broken.example/feed": ConnectionError("boom"),
        "https://www.googleapis.com/youtube/v3/search": fixture("youtube_search.json"),
        "https://www.googleapis.com/youtube/v3/videos": fixture("youtube_videos.json"),
    })


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.env = mock.patch.dict(os.environ, {"TGV_YOUTUBE_API_KEY": "dummy"})
        self.env.start()
        self.report = pipeline.discover(self.conn, CONFIG, http(), NOW, connectors=connectors())
        pipeline.analyze(self.conn, CONFIG, NOW)

    def tearDown(self):
        self.env.stop()

    def rows(self):
        return {r["title"]: r for r in self.conn.execute("SELECT * FROM items")}

    def test_failures_are_isolated_and_logged(self):
        status = {r["source"]: r["status"] for r in self.report}
        self.assertEqual(status["Broken"], "error")
        self.assertEqual(status["Outlet A"], "ok")
        self.assertEqual(status["youtube"], "ok")
        alert = self.conn.execute("SELECT * FROM alerts WHERE level='error'").fetchone()
        self.assertIn("ConnectionError", alert["message"])

    def test_quota_is_recorded(self):
        self.assertEqual(db.usage_today(self.conn, NOW, "youtube"), 101)

    def test_story_cluster_and_coverage(self):
        r = self.rows()
        a = r["GTA 6 trailer 3 release date announced by Rockstar"]
        b = r["Rockstar announces GTA VI trailer 3 release date"]
        self.assertEqual(a["cluster_id"], b["cluster_id"])
        self.assertEqual(json.loads(a["score_breakdown"])["coverage"], 0.25)

    def test_statuses(self):
        r = self.rows()
        self.assertEqual(r["Best cozy farming games of the year"]["status"], "discarded")
        self.assertEqual(r["GTA 6 map leak reportedly shows all of Leonida"]["status"], "review")
        self.assertEqual(r["GTA VI Lucia edit #shorts"]["status"], "review")  # CC licence must be checked
        self.assertEqual(r["Grand Theft Auto VI Trailer 3"]["claim_status"], "confirmed")

    def test_rediscovery_adds_snapshot_not_duplicate(self):
        later = NOW + timedelta(hours=2)
        pipeline.discover(self.conn, CONFIG, http(), later, connectors=connectors())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 7)
        vid = self.rows()["GTA 6: 10 details you missed in trailer 3"]["id"]
        n = self.conn.execute("SELECT COUNT(*) FROM metric_snapshots WHERE item_id=?", (vid,)).fetchone()[0]
        self.assertEqual(n, 2)

    def test_select_one_per_story_and_never_review_items(self):
        chosen = pipeline.select(self.conn, CONFIG, limit=10)
        clusters = [c["cluster_id"] for c in chosen]
        self.assertEqual(len(clusters), len(set(clusters)))
        self.assertTrue(all(c["modality"] in ("B", "C") for c in chosen))
        titles = {c["title"] for c in chosen}
        self.assertNotIn("GTA 6 map leak reportedly shows all of Leonida", titles)
        # selecting again does not pick another item from an already selected story
        again = pipeline.select(self.conn, CONFIG, limit=10)
        self.assertFalse({c["cluster_id"] for c in again} & set(clusters))

    def test_ranking_shows_one_item_per_story(self):
        ranked = pipeline.ranking(self.conn, 50)
        ids = [r["cluster_id"] for r in ranked]
        self.assertEqual(len(ids), len(set(ids)))
        scores = [r["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("Grand Theft Auto VI Trailer 3", [r["title"] for r in ranked[:3]])

    def test_dashboard_renders_and_escapes(self):
        self.conn.execute("UPDATE items SET title='<script>x</script> GTA 6'")
        page = dashboard.render(self.conn, NOW)
        self.assertIn("Melhores oportunidades", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>x", page)
        self.assertIn("Receita confirmada", page)
        self.assertNotIn("dummy", page)  # credentials never reach output


class CliTest(unittest.TestCase):
    def test_init_import_analyze_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbp, out = str(Path(tmp) / "t.db"), str(Path(tmp) / "d.html")
            csvp = str(Path(__file__).parent / "fixtures" / "manual.csv")
            with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                self.assertEqual(cli_main(["--db", dbp, "init"]), 0)
                self.assertEqual(cli_main(["--db", dbp, "import-csv", csvp]), 0)
                self.assertEqual(cli_main(["--db", dbp, "analyze"]), 0)
                self.assertEqual(cli_main(["--db", dbp, "dashboard", "--out", out]), 0)
            self.assertIn("Vice City beach", Path(out).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
