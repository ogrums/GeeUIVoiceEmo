import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("emo_server", Path(__file__).with_name("emo_server.py"))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class LabelTest(unittest.TestCase):
    def test_emotion2vec_order_maps_to_six_labels(self):
        names = server.ONNX_LABELS
        mapped = [server.parse_label(name) for name in names]
        self.assertEqual([
            "angry", "neutral", "fear", "happy", "neutral", "neutral", "sad",
            "surprise", "neutral",
        ], mapped)
        self.assertEqual(names[2], "fearful")
        self.assertEqual(names[7], "surprised")


class ProviderTest(unittest.TestCase):
    def test_picks_first_available_accelerator(self):
        self.assertEqual(["ROCMExecutionProvider"], server.select_providers([
            "AzureExecutionProvider", "ROCMExecutionProvider", "CPUExecutionProvider",
        ]))

    def test_cpu_fallback_and_override(self):
        self.assertEqual(["CPUExecutionProvider"], server.select_providers(["CPUExecutionProvider"]))
        self.assertEqual(["custom", "CPUExecutionProvider"], server.select_providers(
            ["CUDAExecutionProvider"], "custom,CPUExecutionProvider"
        ))


class FusionTest(unittest.TestCase):
    def test_sixty_forty_weights_and_threshold(self):
        self.assertEqual(("sad", 0.54), server.ReactionFusion().fuse(
            ("sad", 0.9), ("happy", 0.9), now=10
        ))
        self.assertEqual("neutral", server.ReactionFusion().fuse(
            ("angry", 0.8), ("happy", 0.8), now=10
        )[0])
        self.assertEqual("neutral", server.ReactionFusion().fuse(
            ("happy", 0.8), ("neutral", 0.0), now=10
        )[0])

    def test_cooldown_applies_only_to_non_neutral(self):
        fused = server.ReactionFusion(cooldown_s=4)
        self.assertEqual("happy", fused.fuse(("happy", 1), ("happy", 1), now=10)[0])
        self.assertEqual("neutral", fused.fuse(("sad", 1), ("sad", 1), now=11)[0])
        self.assertEqual("neutral", fused.fuse(("neutral", 1), ("neutral", 1), now=12)[0])
        self.assertEqual("sad", fused.fuse(("sad", 1), ("sad", 1), now=14)[0])


if __name__ == "__main__":
    unittest.main()
