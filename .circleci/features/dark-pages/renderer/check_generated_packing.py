"""Audit exact generator outputs, not substitute structs for full Blink compilation.
Usage: python check_generated_packing.py BASELINE_DIR BROKEN_DIR FIXED_DIR
Each directory must contain computed_style_base.h/.cc from the pinned generator.
"""
import pathlib
import re
import subprocess
import sys
import tempfile


def audit(dirs):
    source = '#include <cstdio>\n'
    blocks = []
    for name, directory in zip(('baseline', 'broken', 'fixed'), dirs):
        header = (pathlib.Path(directory) / 'computed_style_base.h').read_text()
        data = header.split('  struct Data {', 1)[1].split('  };', 1)[0]
        group = header.split('  class StyleInheritedData :', 1)[1].split('\n  };', 1)[0]
        bits = '\n'.join(x for x in group.splitlines() if re.search(r'unsigned .* : \d+;', x))
        storage = header.split('  // Storage.', 1)[1].split('\n};', 1)[0]
        blocks.append((data, bits, storage))
        source += f'struct {name} {{{data}\n}};\nstruct {name}_inherited {{{bits}\n}};\n'
        if name == 'fixed':
            for field in ('sandium_manual_color_override_', 'sandium_palette_enabled_'):
                assert field not in data
                assert field in bits
                assert f'{field} == other.{field}' in group
                assert f'Access(inherited_data_, access_.inherited_data_)->{field}' in header
            assert 'Member<StyleInheritedData> inherited_data_;' in storage
    assert blocks[0][0] == blocks[2][0], 'Root bitfields must exactly match baseline'
    assert blocks[0][2] == blocks[2][2], 'Root storage must exactly match baseline'
    source += '''int main() {
      static_assert(sizeof(baseline) == sizeof(fixed));
      static_assert(sizeof(broken) == sizeof(baseline) + 4);
      static_assert(sizeof(baseline_inherited) == sizeof(fixed_inherited));
      printf("generated root bitfield bytes: %zu / %zu / %zu; inherited: %zu / %zu / %zu\\n",
        sizeof(baseline), sizeof(broken), sizeof(fixed),
        sizeof(baseline_inherited), sizeof(broken_inherited), sizeof(fixed_inherited));
    }\n'''
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp)
        (path / 'check.cc').write_text(source)
        subprocess.run(['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror', str(path / 'check.cc'), '-o', str(path / 'check')], check=True)
        subprocess.run([str(path / 'check')], check=True)
    print('Exact generated storage compared. NOT a full Blink/Android compilation.')

if __name__ == '__main__':
    assert len(sys.argv) == 4, __doc__
    audit(sys.argv[1:])
