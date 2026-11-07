import unittest
from datetime import datetime, timedelta, timezone

from tgv.scoring import Snapshot, growth_per_hour, international_signal, score

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def s(hours_ago, views, likes=None, comments=None):
    return Snapshot(NOW - timedelta(hours=hours_ago), views, likes, comments)


class ScoringTest(unittest.TestCase):
    def common(self, **kw):
        base = dict(published_at=NOW - timedelta(hours=6), now=NOW, relevance=1.0, category="video_trend",
                    language="en", country=None, cluster_sources=1, snapshots=[])
        base.update(kw)
        return score(**base)

    def test_faster_video_scores_higher(self):
        fast, _ = self.common(snapshots=[s(0, 600_000, 30_000)])
        slow, _ = self.common(snapshots=[s(0, 6_000, 300)])
        self.assertGreater(fast, slow)

    def test_brazilian_content_is_deprioritised(self):
        intl, _ = self.common(snapshots=[s(0, 100_000)])
        br, _ = self.common(snapshots=[s(0, 100_000)], language="pt")
        self.assertGreater(intl, br)

    def test_coverage_and_recency_for_articles(self):
        many, bd = self.common(category="press_news", cluster_sources=5)
        one, _ = self.common(category="press_news", cluster_sources=1)
        old, _ = self.common(category="press_news", cluster_sources=1, published_at=NOW - timedelta(days=3))
        self.assertGreater(many, one)
        self.assertGreater(one, old)
        self.assertNotIn("velocity", bd)

    def test_relevance_zero_scores_zero(self):
        total, _ = self.common(relevance=0.0, snapshots=[s(0, 10_000_000)])
        self.assertEqual(total, 0.0)

    def test_growth_uses_last_two_snapshots(self):
        self.assertEqual(growth_per_hour([s(2, 1000), s(1, 3000)]), 2000)
        self.assertIsNone(growth_per_hour([s(1, 1000)]))
        self.assertEqual(growth_per_hour([s(2, 5000), s(1, 4000)]), 0.0)

    def test_score_bounded(self):
        total, _ = self.common(category="official_news", cluster_sources=9, published_at=NOW - timedelta(minutes=5),
                               snapshots=[s(1, 1, 1), s(0, 10**9, 10**8, 10**7)])
        self.assertLessEqual(total, 100)
        self.assertGreater(total, 90)

    def test_international_signal(self):
        self.assertEqual(international_signal("pt", None), 0.2)
        self.assertEqual(international_signal(None, "BR"), 0.2)
        self.assertEqual(international_signal("en", "US"), 1.0)


if __name__ == "__main__":
    unittest.main()
