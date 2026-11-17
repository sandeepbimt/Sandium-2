"""DictValue iterators yield proxy pairs by value, not pair lvalue references.

Pinned Chromium d331de35 base/value_iterators.h defines both reference and
value_type as pair<const string&, [const] Value&>, and operator* returns reference.
The pair can be copied without copying either referenced object.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.circleci/features/element-corrector/native/element_color_rule_store.cc'

class DictIterationTypes(unittest.TestCase):
    def test_store_uses_value_proxy_bindings(self):
        source = SOURCE.read_text()
        self.assertIn('for (const auto [key, value] : sites)', source)
        self.assertIn('for (const auto [origin, value] : *incoming)', source)
        self.assertNotRegex(source, r'for\s*\(const auto&\s*\[')

    def test_actual_loop_declarations_preserve_reference_semantics(self):
        declarations = re.findall(r'for \((const auto \[[^]]+\]) : (?:sites|\*incoming)\)', SOURCE.read_text())
        self.assertEqual(2, len(declarations))
        code = r'''
#include <cassert>
#include <string>
#include <type_traits>
#include <utility>
struct Value { Value() = default; Value(const Value&) = delete; int number = 7; };
template<class T> struct Range {
  std::string key = "site";
  Value value;
  struct Iterator {
    Range* range; bool end;
    using reference = std::pair<const std::string&, T&>;
    reference operator*() const { return {range->key, range->value}; }
    Iterator& operator++() { end = true; return *this; }
    bool operator!=(const Iterator& other) const { return end != other.end; }
  };
  Iterator begin() { return {this, false}; }
  Iterator end() { return {this, true}; }
};
int main() {
  Range<const Value> sites;
  for (CONST_DECL : sites) {
    static_assert(std::is_same_v<decltype(key), const std::string&>);
    static_assert(std::is_same_v<decltype(value), const Value&>);
    assert(&key == &sites.key && &value == &sites.value);
  }
  Range<Value> incoming;
  for (MUTABLE_DECL : incoming) {
    static_assert(std::is_same_v<decltype(origin), const std::string&>);
    static_assert(std::is_same_v<decltype(value), Value&>);
    assert(&origin == &incoming.key && &value == &incoming.value);
    value.number = 9;
  }
  assert(incoming.value.number == 9);
}
'''.replace('CONST_DECL', declarations[0]).replace('MUTABLE_DECL', declarations[1])
        compiler = shutil.which('clang++') or shutil.which('g++')
        self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'probe.cc'; source.write_text(code)
            binary = Path(td) / 'probe'
            flags = ['-std=c++20', '-Wall', '-Wextra', '-Werror']
            if 'clang' in compiler: flags += ['-Wrange-loop-bind-reference']
            subprocess.run([compiler, *flags, str(source), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True)

if __name__ == '__main__': unittest.main()
