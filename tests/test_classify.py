import unittest
from datetime import datetime, timezone

from tgv.classify import classify, needs_review, relevance
from tgv.models import ContentItem

T = datetime(2026, 11, 6, tzinfo=timezone.utc)


def item(title, **kw):
    base = dict(source="rss", source_name="X", external_id="1", url="https://x/1", title=title, published_at=T)
    base.update(kw)
    return ContentItem(**base)


class RelevanceTest(unittest.TestCase):
    def test_strong_and_weak(self):
        self.assertEqual(relevance("GTA 6 new trailer"), 1.0)
        self.assertEqual(relevance("Grand Theft Auto VI"), 1.0)
        self.assertEqual(relevance("gta-vi pre-orders"), 1.0)
        self.assertEqual(relevance("Rockstar shows Vice City again"), 0.6)
        self.assertEqual(relevance("GTA 5 Online update"), 0.0)
        self.assertEqual(relevance("Cozy farming games"), 0.0)


class ClassifyTest(unittest.TestCase):
    def test_official_is_confirmed_news(self):
        c = classify(item("Grand Theft Auto VI Trailer 3", is_official=True, media_type="video"))
        self.assertEqual((c.category, c.claim_status, c.modality), ("official_news", "confirmed", "C"))

    def test_press_is_reported_not_confirmed(self):
        c = classify(item("GTA 6 trailer 3 release date announced"))
        self.assertEqual((c.category, c.claim_status, c.modality), ("press_news", "reported", "C"))
        self.assertFalse(needs_review(c))

    def test_rumor_and_leak_go_to_review(self):
        c = classify(item("GTA 6 map leak reportedly shows Leonida"))
        self.assertEqual(c.claim_status, "unverified")
        self.assertIn("leak_content", c.flags)
        self.assertTrue(needs_review(c))

    def test_portuguese_rumor_words(self):
        c = classify(item("Boato: GTA 6 vai ter mapa gigante", language="pt"))
        self.assertEqual(c.claim_status, "unverified")
        self.assertIn("brazilian_source", c.flags)

    def test_creative_commons_is_only_a_candidate(self):
        c = classify(item("GTA VI edit", source="youtube", media_type="short", license="creativeCommon"))
        self.assertEqual(c.modality, "A_candidate")
        self.assertIn("license_review", c.flags)
        self.assertTrue(needs_review(c))

    def test_standard_video_is_reference_only(self):
        c = classify(item("GTA 6 details you missed", source="youtube", media_type="video", license="youtube"))
        self.assertEqual(c.modality, "B")
        self.assertIn("third_party_media", c.flags)

    def test_irrelevant_is_skipped(self):
        self.assertEqual(classify(item("Best farming games")).modality, "skip")


if __name__ == "__main__":
    unittest.main()
