import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tgv.production.brand import load_brand
from tgv.production.library import LibraryError, credits, load_library, rights_summary, select_assets
from tgv.production.render import build_command

ROOT = Path(__file__).resolve().parent.parent
BRAND = load_brand(ROOT / "config" / "brand.json")


def entry(**kw):
    base = dict(file="clip.mp4", kind="clip", tags=["GTA VI", "gta 6"], source_url="https://www.rockstargames.com/VI",
                rights_basis="rockstar_fan_policy", credit="Rockstar Games")
    base.update(kw)
    return base


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def write(self, *entries, touch=True):
        for e in entries:
            if touch:
                (self.tmp / e["file"]).write_bytes(b"x")
        path = self.tmp / "library.json"
        path.write_text(json.dumps({"assets": list(entries)}), encoding="utf-8")
        return path

    def test_missing_manifest_is_empty(self):
        self.assertEqual(load_library(self.tmp / "nope.json"), [])

    def test_example_manifest_is_valid(self):
        self.assertEqual(len(load_library(ROOT / "config" / "media_library.example.json")), 3)

    def test_fan_policy_is_never_commercial(self):
        [a] = load_library(self.write(entry(commercial_ok=True)))
        self.assertFalse(a.commercial_ok)
        basis, commercial = rights_summary([a])
        self.assertFalse(commercial)
        self.assertIn("rockstar_fan_policy", basis)

    def test_own_is_commercial_by_default(self):
        [a] = load_library(self.write(entry(rights_basis="own", source_url="")))
        self.assertTrue(a.commercial_ok)

    def test_invalid_entries_raise(self):
        for bad in (entry(rights_basis="youtube_download"), entry(source_url=""), entry(credit=""),
                    entry(rights_basis="licensed"), entry(tags=["gta vi", "leak"]), entry(kind="gif"),
                    entry(tags=[])):
            with self.subTest(bad=bad), self.assertRaises(LibraryError):
                load_library(self.write(bad))

    def test_selection_matches_tags_prefers_clips_and_skips_missing_files(self):
        path = self.write(entry(file="a.jpg", kind="image"), entry(file="b.mp4"),
                          entry(file="c.mp4", tags=["red dead"]))
        (self.tmp / "gone.mp4").unlink(missing_ok=True)
        assets = load_library(path)
        picked = select_assets(assets, "Trailer 3 de GTA VI tem data", limit=4)
        self.assertEqual([Path(a.file).name for a in picked], ["b.mp4", "a.jpg"])
        self.assertEqual(select_assets(assets, "Novo Zelda anunciado"), [])
        self.assertEqual(credits(picked), "Rockstar Games")
        (self.tmp / "b.mp4").unlink()
        self.assertEqual([Path(a.file).name for a in select_assets(assets, "gta 6")], ["a.jpg"])

    def test_render_uses_visuals_without_their_audio(self):
        cmd = build_command(brand=BRAND, audio="n.wav", ass="c.ass", out="v.mp4", seconds=10, claim_status="reported",
                            visuals=[("t.mp4", "clip", 12.0), ("s.jpg", "image", 0.0)])
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("-stream_loop", cmd)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "12.000")
        self.assertIn("concat=n=2:v=1:a=0[bg]", graph)
        self.assertIn("[2:a]loudnorm", graph)  # audio comes from the narration input only
        self.assertEqual(cmd[cmd.index("-map", cmd.index("-map") + 1) + 1], "[a]")


class ClipFormatTest(unittest.TestCase):
    """The page decides per item: visual clips go out with their own audio, text-heavy news is narrated."""

    def draft(self, **kw):
        from tgv.production.script import ScriptDraft, Segment
        base = dict(title="GTA 5 com DLSS 5", format="clip", claim_status="reported",
                    segments=[Segment("", "GTA 5 com DLSS 5")], caption="Olha isso. Fonte: IGN",
                    hashtags=["gta"], sources=["https://www.ign.com/x"], cover_text="GTA 5 com DLSS 5")
        base.update(kw)
        return ScriptDraft(**base)

    def test_clip_needs_a_clip(self):
        from tgv.production.script import validate_script
        self.assertTrue(validate_script(self.draft(), item_url="https://www.ign.com/x", item_claim_status="reported",
                                        clip_available=True).ok)
        v = validate_script(self.draft(), item_url="https://www.ign.com/x", item_claim_status="reported")
        self.assertIn("clip format needs", " ".join(v.errors))

    def test_rumor_is_never_clip(self):
        from tgv.production.script import validate_script
        d = self.draft(claim_status="unverified", cover_text="Rumor: DLSS 5", caption="Rumor. Fonte: IGN")
        v = validate_script(d, item_url="https://www.ign.com/x", item_claim_status="unverified", clip_available=True)
        self.assertIn("rumors are always narrated", " ".join(v.errors))

    def test_narrated_format_needs_narration(self):
        from tgv.production.script import validate_script
        v = validate_script(self.draft(format="news"), item_url="https://www.ign.com/x", item_claim_status="reported")
        self.assertIn("empty narration", " ".join(v.errors))

    def test_template_picks_clip_only_when_available(self):
        from tgv.production.script import TemplateScriptWriter
        item = {"source_name": "IGN", "claim_status": "reported", "title": "GTA 5 DLSS 5", "url": "https://www.ign.com/x"}
        self.assertEqual(TemplateScriptWriter().write(dict(item, clip_available=True)).format, "clip")
        self.assertEqual(TemplateScriptWriter().write(item).format, "news")
        self.assertEqual(TemplateScriptWriter().write(dict(item, clip_available=True, claim_status="unverified")).format,
                         "news")

    def test_clip_render_uses_clip_audio(self):
        cmd = build_command(brand=BRAND, audio=None, ass="c.ass", out="v.mp4", seconds=20, claim_status="reported",
                            visuals=[("t.mp4", "clip", 5.0)])
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("[0:a]loudnorm", graph)
        self.assertNotIn("n.wav", cmd)
        with self.assertRaises(ValueError):
            build_command(brand=BRAND, audio=None, ass="c.ass", out="v.mp4", seconds=20, claim_status="reported",
                          visuals=[("s.jpg", "image", 0.0)])


if __name__ == "__main__":
    unittest.main()
