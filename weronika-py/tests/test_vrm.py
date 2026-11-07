import json
import struct
import unittest

from weronika_agent.blueprint import (
    BlueprintError,
    _read_glb_chunks,
    _write_glb,
    describe_vrm_limits,
    glb_to_vrm,
    vrm_meta,
)


def minimal_glb(document=None, binary=b""):
    return _write_glb(document or {"asset": {"version": "2.0"}, "scene": 0}, binary)


class GlbRoundTripTests(unittest.TestCase):
    def test_write_then_read_preserves_the_document(self):
        document = {"asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}], "scene": 0}
        glb = minimal_glb(document, b"\x00\x01\x02\x03")
        parsed, binary = _read_glb_chunks(glb)
        self.assertEqual(parsed, document)
        self.assertEqual(binary, b"\x00\x01\x02\x03")

    def test_chunks_stay_four_byte_aligned(self):
        for size in range(4):
            glb = minimal_glb({"asset": {"version": "2.0"}, "extras": "x" * size}, b"a" * size)
            self.assertEqual(len(glb) % 4, 0, size)
            self.assertGreaterEqual(len(glb), 12)

    def test_a_non_glb_payload_is_rejected(self):
        for payload in (b"", b"PNG...", b"glTF" + b"\x00" * 40):
            with self.assertRaises(BlueprintError):
                _read_glb_chunks(payload)

    def test_a_wrong_version_is_rejected(self):
        bad = b"glTF" + struct.pack("<II", 1, 12)
        with self.assertRaises(BlueprintError):
            _read_glb_chunks(bad)


class VrmExportTests(unittest.TestCase):
    def test_export_produces_a_valid_vrm_container(self):
        vrm = glb_to_vrm(minimal_glb(), "My avatar")
        document, binary = _read_glb_chunks(vrm)
        self.assertIn("VRM", document["extensionsUsed"])
        block = document["extensions"]["VRM"]
        self.assertEqual(block["specVersion"], "0.x")
        self.assertEqual(block["meta"]["title"], "My avatar")
        self.assertEqual(block["exporterVersion"], "Weronika-Blueprint 1.0")
        self.assertEqual(binary, b"")

    def test_export_is_honest_about_the_missing_rig(self):
        vrm = glb_to_vrm(minimal_glb())
        block = _read_glb_chunks(vrm)[0]["extensions"]["VRM"]
        self.assertFalse(block["rigged"])
        self.assertEqual(block["humanoid"]["humanBones"], [])
        self.assertEqual(block["blendShapeMaster"]["blendShapeGroups"], [])
        self.assertIn("no skeleton", block["note"].lower())

    def test_mesh_data_survives_the_export(self):
        glb = minimal_glb(
            {"asset": {"version": "2.0"}, "meshes": [{"name": "photo"}], "scene": 0},
            b"mesh-bytes",
        )
        document, binary = _read_glb_chunks(glb_to_vrm(glb))
        self.assertEqual(document["meshes"], [{"name": "photo"}])
        # GLB pads the binary chunk to a 4-byte boundary.
        self.assertEqual(binary.rstrip(b"\x00"), b"mesh-bytes")

    def test_metadata_blocks_commercial_and_sexual_use(self):
        meta = vrm_meta("t")
        self.assertEqual(meta["commercialUssageName"], "Disallow")
        self.assertEqual(meta["sexualUssageName"], "Disallow")
        self.assertEqual(meta["violentUssageName"], "Disallow")
        self.assertEqual(meta["allowedUserName"], "OnlyAuthor")

    def test_garbage_input_is_refused(self):
        with self.assertRaises(BlueprintError):
            glb_to_vrm(b"not a model")

    def test_limits_are_reported_to_the_orb(self):
        limits = describe_vrm_limits()
        self.assertTrue(limits["static"])
        self.assertFalse(limits["rigged"])
        self.assertFalse(limits["has_blendshapes"])
        self.assertIn("cannot be posed", limits["note"])


if __name__ == "__main__":
    unittest.main()
