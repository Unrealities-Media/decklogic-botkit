import pathlib
import tempfile
import unittest

from smoke import CORE, OPTIONAL, sdk_symbols


class HeaderOwnership(unittest.TestCase):
    def test_actual_headers_have_distinct_guards_and_cpp_linkage(self):
        include = pathlib.Path(__file__).resolve().parents[1] / "simlib/include"
        core = (include / "decklogic_simlib_core.h").read_text()
        facade = (include / "decklogic_simlib.h").read_text()
        self.assertIn("#ifndef DECKLOGIC_SIMLIB_CORE_H\n#define DECKLOGIC_SIMLIB_CORE_H", core)
        self.assertIn("#ifndef DECKLOGIC_SIMLIB_H\n#define DECKLOGIC_SIMLIB_H", facade)
        self.assertNotIn("#define DECKLOGIC_SIMLIB_H\n", core)
        self.assertNotIn("typedef struct", facade)
        for text in (core, facade):
            self.assertIn('#ifdef __cplusplus\nextern "C" {\n#endif', text)
            self.assertIn('#ifdef __cplusplus\n}\n#endif', text)
        self.assertLess(facade.index('#include "decklogic_simlib_core.h"'),
                        facade.index('extern "C"'))
        required, extensions = sdk_symbols(include)
        self.assertTrue(CORE <= required)
        self.assertEqual(extensions, OPTIONAL)

    def test_core_and_extensions_are_combined_without_inventing_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            core = root / "decklogic_simlib_core.h"
            facade = root / "decklogic_simlib.h"
            core.write_text("\n".join(f"void {name}(void);" for name in CORE))
            facade.write_text('#include "decklogic_simlib_core.h"\n' +
                              "\n".join(f"void {name}(void);" for name in OPTIONAL))
            required, extensions = sdk_symbols(root)
            self.assertEqual(required, CORE)
            self.assertEqual(extensions, OPTIONAL)
            core.unlink()
            with self.assertRaisesRegex(RuntimeError, "regular files"):
                sdk_symbols(root)

    def test_facade_cannot_hide_core_or_include_unchecked_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "decklogic_simlib_core.h").write_text("void dls_info(void);")
            for include in ('', '#include "other.h"',
                            '#include "decklogic_simlib_core.h"\n#include "extra.h"'):
                (root / "decklogic_simlib.h").write_text(include)
                with self.assertRaisesRegex(RuntimeError, "exactly"):
                    sdk_symbols(root)


if __name__ == "__main__":
    unittest.main()
