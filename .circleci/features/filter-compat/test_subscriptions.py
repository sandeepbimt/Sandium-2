"""Exercise the actual C++ preparser injected into the subscription provider."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import subscriptions


class SubscriptionConditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.executable = Path(cls.temp.name) / "subscription-test"
        test_source = r'''
#include <cstdint>
#include <cstring>
#include <iostream>
#include <iterator>
#include <optional>
#include <string_view>
#include <vector>
using DATFileDataBuffer = std::vector<unsigned char>;
''' + subscriptions.HELPERS + r'''
int main() {
  DATFileDataBuffer buf(std::istreambuf_iterator<char>(std::cin), {});
  auto storage = buf.data();
  PruneSandiumSubscription(buf);
  if (storage != buf.data()) return 1;
  for (const auto c : buf) std::cout.put(c);
}
'''
        subprocess.run(["c++", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-x", "c++", "-", "-o", cls.executable],
                       input=test_source, text=True, check=True)

    def prune(self, raw):
        return subprocess.check_output([self.executable], input=raw)

    def active(self, text):
        output = self.prune(text.encode())
        return [line for line in output.decode().splitlines()
                if line and not line.startswith("!")]

    def test_plain_lists_and_input_boundaries(self):
        source = b"[Adblock Plus 2.0]\r\n! Title: A\r\n||ads.example^\n"
        for data in [b"", source, source + b"! comment about !#if env_firefox"]:
            self.assertEqual(self.prune(data), data)
        raw = b"!#if cap_html_filtering\r\n! Title: Wrong\r\nDROP\r\n!#endif\r\nOK"
        self.assertEqual(self.prune(raw), b"\r\n\r\n\r\n!#endif\r\nOK")

    def test_dialect_and_unknown_tokens(self):
        cases = {
            "env_chromium": ["T"], "env_mobile": ["T"], "env_brave": ["T"],
            "ext_ublock": ["T"], "adguard_ext_chromium": ["T"], "ext_ubol": ["F"],
            "env_firefox": ["F"], "cap_html_filtering": ["F"], "cap_ipaddress": ["F"],
            "!cap_future": ["T"], "cap_future": ["F"], "future_engine": ["T", "F"],
            "!future_engine": ["T", "F"], "": ["T", "F"], "false": ["F"],
            "(!env_firefox && env_mobile)": ["T"], "env_firefox || env_mobile && false": ["F"],
            "ext_ublock || future_engine": ["T", "F"], "future_engine || env_mobile": ["T"],
            "future_engine && false": ["T", "F"], "env_mobile + env_chromium": ["T", "F"],
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(self.active(f"!#if {expression}\nT\n!#else\nF\n!#endif\n"), expected)

    def test_nested_and_malformed_blocks(self):
        self.assertEqual(self.active("!#if env_firefox\nX\n!#if env_mobile\nY\n!#else\n"
                                     "Z\n!#endif\n!#else\nA\n!#if cap_missing\nX\n"
                                     "!#else\nB\n!#endif\n!#endif\nC"), ["A", "B", "C"])
        self.assertEqual(self.active("!#else\nA\n!#endif\nB\n!#if false\nC"), ["A", "B"])
        self.assertEqual(self.active("!#ifx false\nA\n!#endif_\nB"), ["A", "B"])
        self.assertEqual(self.active("!#if false\nX\n!#else\nA\n!#else\nY\n!#endif\nB"),
                         ["A", "B"])

    def test_exact_once_overlay(self):
        source = subscriptions.INCLUDE + subscriptions.FUNCTION + "\n" + subscriptions.PARSE
        updated = subscriptions.transform(source)
        self.assertEqual(subscriptions.transform(updated), updated)
        for partial in [updated.replace(subscriptions.CALL, subscriptions.PARSE),
                        source + subscriptions.PARSE]:
            with self.assertRaises(ValueError):
                subscriptions.transform(partial)


if __name__ == "__main__":
    unittest.main()
