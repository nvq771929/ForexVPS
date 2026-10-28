"""Targeted MQL declaration check; C++ allows final/override as identifiers.

This regression check does not replace compilation with MetaEditor.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NON_CODE = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
RESERVED_DECLARATION = re.compile(
    r'\b(?:bool|char|uchar|short|ushort|int|uint|long|ulong|float|double|string|datetime|color)'
    r'\s+(?:&\s*)?(final|override)\b'
)


def reserved_declarations(source):
    code = NON_CODE.sub(lambda match: '\n' * match[0].count('\n') + ' ', source)
    return [(match[1], code.count('\n', 0, match.start()) + 1)
            for match in RESERVED_DECLARATION.finditer(code)]


class MQLReservedIdentifierTests(unittest.TestCase):
    def test_detects_reported_parameter_and_local_declarations(self):
        self.assertEqual(reserved_declarations(
            'void State(bool final=false) {\n int override=0;\n}'),
            [('final', 1), ('override', 2)])

    def test_ignores_literals_comments_and_longer_identifiers(self):
        self.assertEqual(reserved_declarations(
            '// bool final=false\n/* int override; */\n'
            'string label="bool final=false"; char q=\'f\';\n'
            'void State(bool isFinal=false) { int finalCount=0; }'), [])

    def test_native_sources_do_not_declare_cpp_contextual_keywords(self):
        for path in sorted((ROOT / 'mt4').rglob('*')):
            if path.suffix not in ('.mq4', '.mqh'):
                continue
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertEqual(reserved_declarations(path.read_text()), [])


if __name__ == '__main__':
    unittest.main()
