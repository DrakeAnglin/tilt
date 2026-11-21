#!/usr/bin/env python3
"""Pack the web app (firmware/blinds/ui/index.html + its scripts) into firmware/blinds/ui.h (one gzipped page)."""
import gzip, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, '..', 'firmware', 'blinds', 'ui')

def page():
    html = open(os.path.join(UI, 'index.html')).read()
    def inline(m):
        return '<script>' + open(os.path.join(UI, m.group(1))).read() + '</script>'
    return re.sub(r'<script src="([^"]+)"></script>', inline, html)

if __name__ == '__main__':
    raw = page().encode()
    gz = gzip.compress(raw, 9, mtime=0)
    rows = [', '.join(str(b) for b in gz[i:i + 24]) for i in range(0, len(gz), 24)]
    out = ('// Made by tools/build_ui.py from ui/index.html. Do not edit.\n#pragma once\n#include <Arduino.h>\n'
           'const size_t UI_GZ_LEN = %d;\nconst uint8_t UI_GZ[] PROGMEM = {\n%s\n};\n' % (len(gz), ',\n'.join(rows)))
    open(os.path.join(UI, '..', 'ui.h'), 'w').write(out)
    print('ui.h: %d bytes of page -> %d bytes gzipped' % (len(raw), len(gz)))
