import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tgv.dedup import assign_clusters, canonical_key


@dataclass
class R:
    id: int
    title: str
    published_at: datetime


T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


class CanonicalKeyTest(unittest.TestCase):
    def test_youtube_shapes_collapse(self):
        keys = {canonical_key(u) for u in (
            "https://www.youtube.com/watch?v=AAAAAAAAAAA&feature=share",
            "https://youtu.be/AAAAAAAAAAA?si=xyz",
            "https://m.youtube.com/shorts/AAAAAAAAAAA",
            "https://www.youtube.com/embed/AAAAAAAAAAA",
        )}
        self.assertEqual(keys, {"youtube:AAAAAAAAAAA"})

    def test_reddit_shapes_collapse(self):
        self.assertEqual(canonical_key("https://old.reddit.com/r/GTA6/comments/DEF456/title/"), "reddit:def456")
        self.assertEqual(canonical_key("https://www.reddit.com/r/GTA6/comments/def456/"), "reddit:def456")

    def test_tracking_params_removed_real_params_kept(self):
        a = canonical_key("https://www.site.com/a/?utm_source=x&page=2&fbclid=1")
        b = canonical_key("http://site.com/a?page=2")
        self.assertEqual(a, b)
        self.assertNotEqual(canonical_key("https://site.com/a?sid=1"), canonical_key("https://site.com/a"))


class ClusterTest(unittest.TestCase):
    def test_same_story_clusters(self):
        rows = [
            R(1, "GTA 6 trailer 3 release date announced by Rockstar", T0),
            R(2, "Rockstar announces GTA VI trailer 3 release date", T0 + timedelta(hours=1)),
            R(3, "GTA 6 map leak shows all of Leonida", T0),
        ]
        c = assign_clusters(rows)
        self.assertEqual(c[1], c[2])
        self.assertNotEqual(c[1], c[3])

    def test_window_splits_old_stories(self):
        rows = [R(1, "GTA 6 trailer 3 release date announced", T0),
                R(2, "GTA 6 trailer 3 release date announced", T0 + timedelta(days=5))]
        c = assign_clusters(rows, window_hours=72)
        self.assertNotEqual(c[1], c[2])

    def test_short_titles_need_exact_match(self):
        rows = [R(1, "GTA 6 Lucia", T0), R(2, "GTA 6 Jason", T0)]
        c = assign_clusters(rows)
        self.assertNotEqual(c[1], c[2])


if __name__ == "__main__":
    unittest.main()
