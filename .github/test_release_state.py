import copy
import unittest

from release_state import classify, latest_policy, required_assets


class ReleaseState(unittest.TestCase):
    def setUp(self):
        self.tag = "sim-engine-v213-kit-0123456789abcdef"
        self.release = {
            "tag_name": self.tag, "draft": False, "prerelease": False,
            "published_at": "2026-11-13T00:00:00Z",
            "assets": [{"name": name, "state": "uploaded", "size": 42}
                       for name in sorted(required_assets(self.tag))],
        }

    def test_absent_and_complete_across_pages(self):
        self.assertEqual(classify([[]], self.tag), "absent")
        self.assertEqual(classify([[{"tag_name": "old"}], [self.release]], self.tag), "complete")

    def test_unpublished_or_prerelease_requires_recovery(self):
        for field, value in (("draft", True), ("prerelease", True), ("published_at", None)):
            with self.subTest(field=field):
                release = dict(self.release, **{field: value})
                with self.assertRaisesRegex(ValueError, "authorized operator"):
                    classify([[release]], self.tag)

    def test_each_asset_required_and_uploaded_nonempty_unique(self):
        for index in range(5):
            for fault in ("missing", "duplicate", "empty", "starter", "invalid-size"):
                with self.subTest(index=index, fault=fault):
                    release = copy.deepcopy(self.release)
                    asset = release["assets"][index]
                    if fault == "missing":
                        release["assets"].pop(index)
                    elif fault == "duplicate":
                        release["assets"].append(asset)
                    elif fault == "empty":
                        asset["size"] = 0
                    elif fault == "starter":
                        asset["state"] = "starter"
                    else:
                        asset["size"] = True
                    with self.assertRaisesRegex(ValueError, "authorized operator"):
                        classify([[release]], self.tag)

    def test_invalid_metadata_does_not_prove_absence(self):
        for metadata in ([], {}, [{"message": "API error"}], [[{}]], [[None]]):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                classify(metadata, self.tag)
        with self.assertRaises(ValueError):
            classify([[self.release, self.release]], self.tag)

    def test_latest_policy(self):
        for ref in ("main", "historical-tag", "0123456789abcdef"):
            self.assertFalse(latest_policy("workflow_dispatch", ref))
            self.assertTrue(latest_policy("workflow_dispatch", ref, True))
        self.assertTrue(latest_policy("schedule", "main"))
        for event, ref in (("push", "main"), ("schedule", "historical-tag")):
            with self.assertRaises(ValueError):
                latest_policy(event, ref)
        with self.assertRaises(ValueError):
            latest_policy("workflow_dispatch", "main", "false")


if __name__ == "__main__":
    unittest.main()
