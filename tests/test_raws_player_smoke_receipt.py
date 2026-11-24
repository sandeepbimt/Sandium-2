"""The new player-rule proof is required in addition to the prior engine smoke."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'raws-adblock'))
from native_smoke import CASES, verify_output, verify_port_output


class RawSPlayerSmokeReceipt(unittest.TestCase):
    def test_extension_requires_all_exact_linked_markers(self):
        player = 'RAWS_1471_INCIDENT_RULES_PASS'
        engine = 'RAWS_ENGINE_SMOKE_1442_PASS'
        rotated = 'RAWS_1483_ROTATING_PLAYER_PASS'
        passive = 'RAWS_PASSIVE_SCRIPTLET_NATIVE_PASS'
        good = [rotated, player, passive, engine]
        verify_port_output('\n'.join(good) + '\n')
        wrong_sequences = [
            [engine], [player], [player, engine], [rotated, player, engine],
            [player, rotated, passive, engine], [rotated, player, engine, passive],
            [rotated, player, passive, passive, engine],
            [rotated, player, f'not {passive}', engine],
            [rotated, player, passive, engine, 'extra output'],
        ]
        for wrong in wrong_sequences:
            with self.subTest(output=wrong), self.assertRaises(ValueError):
                verify_port_output('\n'.join(wrong) + '\n')

    def test_unchanged_original_smoke_still_required(self):
        verify_output('\n'.join([f'ok {case}' for case in CASES] + ['RAWS_ENGINE_SMOKE_V2_PASS']))
        with self.assertRaises(ValueError):
            verify_output('RAWS_1471_INCIDENT_RULES_PASS')


if __name__ == '__main__':
    unittest.main()
