"""Pure-logic tests for the tools (no hardware, no network, no slicer).

  python3 -m unittest tools/test_tools.py
The blinds_client tests need the 'cryptography' package (the ESP-IDF python has it); they are skipped without it.
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '../hardware/pcb'))
import bambu  # noqa: E402
import bambu_project  # noqa: E402
import check_docs  # noqa: E402
import firmware_size  # noqa: E402
import netlist  # noqa: E402
import orient  # noqa: E402
import release_ci  # noqa: E402
import release_firmware  # noqa: E402

try:
    import blinds_client
except ImportError:
    blinds_client = None


class ReleaseFirmware(unittest.TestCase):
    def test_der_to_raw(self):
        r, s = b'\x80' + b'\x11' * 31, b'\x00\x22' + b'\x33' * 30      # r needs a leading 0 in DER, s is short
        def integer(v):
            v = v.lstrip(b'\0')
            v = b'\0' + v if v[0] & 0x80 else v
            return b'\x02' + bytes([len(v)]) + v
        body = integer(r) + integer(s)
        self.assertEqual(release_firmware.der_to_raw(b'\x30' + bytes([len(body)]) + body), r + s)


    def test_stable_also_goes_to_beta_unless_beta_is_newer(self):
        e = lambda v: {'version': v, 'file': 'tilt-%s.bin' % v}
        self.assertEqual(release_firmware.add_to_listing({}, 'stable', e('2.3.0'))['beta']['version'], '2.3.0')
        l = release_firmware.add_to_listing({'beta': e('2.3.0-beta2')}, 'stable', e('2.3.0'))
        self.assertEqual(l['beta']['version'], '2.3.0')          # the beta it came from is not newer
        l = release_firmware.add_to_listing({'beta': e('2.4.0-beta1')}, 'stable', e('2.3.1'))
        self.assertEqual(l['beta']['version'], '2.4.0-beta1')    # a newer beta stays
        l = release_firmware.add_to_listing({'stable': e('2.3.0')}, 'beta', e('2.4.0-beta1'))
        self.assertEqual(l['stable']['version'], '2.3.0')        # a beta never touches stable


class ReleaseCI(unittest.TestCase):
    def test_parse_tag(self):
        self.assertEqual(release_ci.parse_tag('fw-v2.3.0'), ('controller', '2.3.0', 'stable'))
        self.assertEqual(release_ci.parse_tag('fw-v2.3.0-beta1'), ('controller', '2.3.0-beta1', 'beta'))
        self.assertEqual(release_ci.parse_tag('hub-v0.3.4'), ('hub', '0.3.4', 'hub'))
        for bad in ['v2.3.0', 'fw-2.3.0', 'fw-v2.3', 'fw-v2.3.0 ', 'firmware-2.3.0']:
            with self.assertRaises(ValueError): release_ci.parse_tag(bad)

    def test_code_versions_parse(self):
        self.assertRegex(release_ci.code_version('controller'), r'^\d+\.\d+\.\d+')
        self.assertRegex(release_ci.code_version('hub'), r'^\d+\.\d+\.\d+')

    def test_raw_to_der_undoes_der_to_raw(self):
        for raw in [b'\x80' + b'\x11' * 31 + b'\x00\x22' + b'\x33' * 30, b'\x01' * 64, b'\x00' * 31 + b'\x05' + b'\xff' * 32]:
            self.assertEqual(release_firmware.der_to_raw(release_ci.raw_to_der(raw)), raw)

    def test_signed_part(self):
        self.assertEqual(release_ci.signed_part(b'IMG' + b's' * 64 + b'TILTSIG1'), (b'IMG', b's' * 64))
        self.assertEqual(release_ci.signed_part(b'P' + b's' * 64 + b'TILTDLT1'), (b'P', b's' * 64))
        with self.assertRaises(ValueError): release_ci.signed_part(b'x' * 80)

    def test_fetch_and_verify_check_only_what_was_built(self):
        """fetch() downloads every file firmware.json names plus older images; verify() then checks only new files."""
        import json, subprocess
        site = {'firmware.json': json.dumps({'stable': {'version': '2.2.0', 'file': 'tilt-2.2.0.bin', 'patches': [{'file': 'tilt-2.2.0-from-2.1.0.patch'}]},
                                             'hub': {'version': '0.3.3', 'file': 'tilt-hub-0.3.3.bin'}}).encode(),
                'tilt-2.1.0.bin': b'old', 'tilt-2.2.0.bin': b'new', 'tilt-2.2.0-from-2.1.0.patch': b'p', 'tilt-hub-0.3.3.bin': b'h'}
        releases = [{'draft': False, 'prerelease': False, 'published_at': '2026-11-0%d' % i,
                     'assets': [{'name': n, 'browser_download_url': 'u:' + n} for n in names]}
                    for i, names in [(1, ['tilt-2.1.0.bin']), (2, list(site))]]
        get = release_ci._get
        release_ci._get = lambda url: json.dumps(releases).encode() if url.startswith('https://api') else site[url[2:]]
        try:
            with tempfile.TemporaryDirectory() as d:
                release_ci.fetch(d)
                self.assertEqual(sorted(release_ci.fetched_names(d)), sorted(n for n in site if n != 'firmware.json'))
                self.assertLess(os.path.getmtime(os.path.join(d, 'tilt-2.1.0.bin')), os.path.getmtime(os.path.join(d, 'tilt-2.2.0.bin')))
                key, pub = os.path.join(d, 'k.pem'), os.path.join(d, 'p.pem')
                subprocess.run(['openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', key], check=True)
                subprocess.run(['openssl', 'ec', '-in', key, '-pubout', '-out', pub], check=True, capture_output=True)
                old_key, release_firmware.KEY = release_firmware.KEY, key
                try:
                    img = b'image' * 50
                    open(os.path.join(d, 'tilt-2.3.0.bin'), 'wb').write(img + release_firmware.sign(img) + b'TILTSIG1')
                finally:
                    release_firmware.KEY = old_key
                release_ci.verify(pub, d)                   # the fetched files are not signed with this key: skipped
                open(os.path.join(d, 'tilt-2.3.0.bin'), 'r+b').write(b'X')
                with self.assertRaises(SystemExit): release_ci.verify(pub, d)
        finally:
            release_ci._get = get

    def test_listed_files_names_every_image_and_patch_once(self):
        listing = {'stable': {'file': 'tilt-2.3.0.bin', 'patches': [{'file': 'tilt-2.3.0-from-2.2.0.patch'}]},
                   'beta': {'file': 'tilt-2.3.0.bin', 'patches': [{'file': 'tilt-2.3.0-from-2.2.0.patch'}]},
                   'hub': {'file': 'tilt-hub-0.3.4.bin'}}
        self.assertEqual(release_ci.listed_files(listing), ['tilt-2.3.0.bin', 'tilt-2.3.0-from-2.2.0.patch', 'tilt-hub-0.3.4.bin'])


class Orient(unittest.TestCase):
    def test_rotations_are_proper(self):
        """Each rotation maps the axes onto the axes (no stretch) and keeps handedness (no mirror)."""
        for name, (rot, mat, row, count, how) in orient.PARTS.items():
            ex, ey, ez = rot(1, 0, 0), rot(0, 1, 0), rot(0, 0, 1)
            for e in (ex, ey, ez):
                self.assertEqual(sorted(abs(c) for c in e), [0, 0, 1], name)
            cross = (ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0])
            self.assertEqual(cross, ez, name + ': mirrored')
            self.assertIn(mat, ('PLA', 'PETG'), name)
            self.assertGreaterEqual(count, 1, name)
            self.assertTrue(how, name)

    def test_copies(self):
        self.assertEqual(orient.copies('planet'), ['planet', 'planet_2', 'planet_3', 'planet_4'])
        self.assertEqual(orient.copies('worm'), ['worm'])


@unittest.skipUnless(os.path.isdir(bambu.PRINT), 'no oriented STLs (run tools/orient.py)')
class BambuPacking(unittest.TestCase):
    BED_SIZE = (350.0, 320.0)                 # H2D: 350 x 320 mm

    def test_rows_cover_every_part(self):
        names = [n for m in ('PLA', 'PETG') for r in bambu.rows(m) for n in r]
        self.assertEqual(sorted(names), sorted(c for n in orient.PARTS for c in orient.copies(n)))

    def test_plates_fit_without_overlap(self):
        for m in ('PLA', 'PETG'):
            rows = bambu.rows(m)
            at = bambu.pack(rows)
            boxes = []
            for n, (x, y) in at.items():
                w, d = bambu.size(n)
                boxes.append((n, x - w / 2, y - d / 2, x + w / 2, y + d / 2))
            for n, x0, y0, x1, y1 in boxes:
                self.assertTrue(0 <= x0 and x1 <= self.BED_SIZE[0] and 0 <= y0 and y1 <= self.BED_SIZE[1], (m, n))
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    apart = a[3] <= b[1] or b[3] <= a[1] or a[4] <= b[2] or b[4] <= a[2]
                    self.assertTrue(apart, (m, a[0], b[0]))


class BambuProject(unittest.TestCase):
    """tools/bambu_project.py: a bulk project, a one-part-per-plate project, per-part brims and supports."""
    EVERY = sorted([c for n in orient.PARTS for c in orient.copies(n)] + list(bambu_project.BOX))
    PLATES = bambu_project.BULK + bambu_project.SINGLE

    def test_every_part_has_its_own_plate(self):
        printed = [n for _, rows in bambu_project.SINGLE for r in rows for n in r]
        self.assertEqual(sorted(printed), self.EVERY)

    def test_bulk_prints_one_tilter_and_the_box_one_material_per_plate(self):
        sets = [n for _, rows in bambu_project.BULK for r in rows for n in r]
        self.assertEqual(sorted(sets), self.EVERY)
        for title, rows in bambu_project.BULK:
            self.assertEqual(len({bambu_project.material(n) for r in rows for n in r}), 1, title)

    def test_plate_names_are_allowed_in_bambu_studio(self):
        for title, _ in self.PLATES:
            self.assertFalse(set(title) & set('<>:/\\|?*"'), title)

    def test_plates_fit_without_overlap(self):
        for title, rows in self.PLATES:
            boxes = []
            for n, (x, y) in bambu_project.pack(rows).items():
                w, d = bambu_project.size(n)
                boxes.append((n, x - w / 2, y - d / 2, x + w / 2, y + d / 2))     # size() includes the brim
            for n, x0, y0, x1, y1 in boxes:
                self.assertTrue(0 <= x0 and x1 <= bambu_project.H2D[0] and 0 <= y0 and y1 <= bambu_project.H2D[1],
                                (title, n))
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    apart = a[3] <= b[1] or b[3] <= a[1] or a[4] <= b[2] or b[4] <= a[2]
                    self.assertTrue(apart, (title, a[0], b[0]))

    def test_supports_only_where_the_owner_said(self):
        on = {n for _, rows in self.PLATES for r in rows for n in r
              if bambu_project.object_settings(n).get('enable_support') == '1'}
        self.assertEqual(on, {'tray_lid', 'worm', 'worm_wheel'})
        self.assertEqual(bambu_project.TWEAKS['enable_support'], '0')

    def test_worm_has_a_brim(self):
        self.assertEqual(bambu_project.object_settings('worm')['brim_type'], 'outer_only')
        self.assertEqual(bambu_project.TWEAKS['brim_type'], 'no_brim')


class Netlist(unittest.TestCase):
    def test_every_net_has_two_pads(self):
        for net, pads in netlist.nets().items():
            self.assertGreaterEqual(len(pads), 2, net)

    def test_no_pad_on_two_nets(self):
        seen = {}
        for net, pads in netlist.nets().items():
            for p in pads:
                self.assertNotIn(p, seen, '%s.%s on %s and %s' % (p + (seen.get(p), net)))
                seen[p] = net

    def test_matches_firmware_config(self):
        self.assertEqual(netlist.check(), [])

    def test_check_catches_a_mismatch(self):
        with open(netlist.CONFIG_H) as f:
            src = f.read().replace('P_EN[PORTS] = {7, 5, 1}', 'P_EN[PORTS] = {7, 5, 9}')
        with tempfile.NamedTemporaryFile('w', suffix='.h', delete=False) as f:
            f.write(src)
        try:
            bad = netlist.check(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(len(bad), 1)
        self.assertTrue(bad[0].startswith('P_EN'))


@unittest.skipUnless(blinds_client, "needs the 'cryptography' package")
class BlindsClient(unittest.TestCase):
    def test_seal_round_trip(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key, cid, boot = bytes(range(32)), b'C' * 8, b'\x01\x02\x03\x04'
        pkt = blinds_client.seal(key, cid, boot, 12345, '/api/s')
        self.assertEqual(pkt[:8], cid)
        nonce = pkt[8:20]
        self.assertEqual(AESGCM(key).decrypt(nonce, pkt[20:], b'blinds-v1' + cid), b'/api/s')
        # the controller's side of a reply, then the client opens it
        rn = b'R' * 12
        raw = rn + AESGCM(key).encrypt(rn, b'{"ok":1}', b'blinds-v1r' + cid + nonce)
        self.assertEqual(blinds_client.open_reply(key, cid, pkt, raw), '{"ok":1}')

    def test_key_derivation_agrees(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        pub = lambda k: k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        a, b = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
        ka = blinds_client.derive_key(a.exchange(ec.ECDH(), b.public_key()), None, pub(a), pub(b))
        kb = blinds_client.derive_key(b.exchange(ec.ECDH(), a.public_key()), None, pub(a), pub(b))
        self.assertEqual(ka, kb)
        self.assertEqual(len(ka), 32)
        self.assertEqual(blinds_client.confirm(ka), blinds_client.confirm(kb))

    def test_link_vectors(self):
        # The hub link's shared vectors (firmware/blinds_matter/test/wire/link.json): the file is what
        # link_vectors.py makes, and this client seals, opens and derives keys the same way.
        import json
        import link_vectors
        path = os.path.join(HERE, '../firmware/blinds_matter/test/wire/link.json')
        with open(path) as f:
            text = f.read()
        self.assertEqual(text, link_vectors.text(), 'regenerate: python3 tools/link_vectors.py > ' + path)
        v = {k: (bytes.fromhex(x) if k not in ('pushJson', 'pushN', 'timeMsg', 'otaMsg', 'salt', 'ctr', 'cmd', 'replyOut') else x)
             for k, x in json.loads(text).items()}
        self.assertEqual(blinds_client.derive_key(v['shared'], None, v['cpub'], v['dpub']), v['key'])
        self.assertEqual(blinds_client.derive_key(v['shared'], v['salt'].encode(), v['cpub'], v['dpub']), v['keySalted'])
        self.assertEqual(blinds_client.seal(v['key'], v['cid'], v['boot'], int(v['ctr']), v['cmd']), v['frame'])
        self.assertEqual(blinds_client.seal(v['keySalted'], v['cid'], v['boot'], int(v['ctr']), v['cmd']), v['frameSalted'])
        self.assertEqual(blinds_client.open_reply(v['key'], v['cid'], v['frame'], v['reply']), v['replyOut'])

    def test_store_is_private(self):
        old = blinds_client.STORE
        with tempfile.TemporaryDirectory() as d:
            blinds_client.STORE = os.path.join(d, 'c.json')
            try:
                blinds_client.save({'x': 1})
                self.assertEqual(os.stat(blinds_client.STORE).st_mode & 0o777, 0o600)
                self.assertEqual(blinds_client.load(), {'x': 1})
            finally:
                blinds_client.STORE = old


class CheckDocs(unittest.TestCase):
    def pages(self, files):
        d = tempfile.mkdtemp()
        for name, text in files.items():
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(text)
        return d

    def test_docs_broken_link(self):
        d = self.pages({'a.md': '# A\n\nSee [gone](gone.md).\n'})
        self.assertEqual(check_docs.problems(d), ['a.md:3: broken link gone.md'])

    def test_docs_bad_anchor(self):
        d = self.pages({'a.md': '[x](other.md#no-such-heading)\n', 'other.md': '# Other\n'})
        self.assertEqual(check_docs.problems(d), ['a.md:1: no heading for #no-such-heading in other.md'])
        d = self.pages({'a.md': '[x](other.md#tilt-hub-one-per-home) [y](#a-b)\n\n## A b\n',
                        'other.md': '## Tilt Hub (one per home)\n'})
        self.assertEqual(check_docs.problems(d), [])

    def test_docs_house_words(self):
        words = 'Buy for 8 blinds on 3 controllers.\n'
        self.assertEqual(len(check_docs.problems(self.pages({'a.md': words}))), 2)
        self.assertEqual(check_docs.problems(self.pages({'a.md': 'Example: ' + words})), [])
        self.assertEqual(check_docs.problems(self.pages({'docs/developer/a.md': words})), [])

    def test_docs_clean(self):
        self.assertEqual(check_docs.problems(os.path.join(HERE, '..')), [])

class FirmwareBuildCI(unittest.TestCase):
    """CI's Tilt Hub build and controller build (.github/workflows/ci.yml, tools/firmware_build_ci.sh)."""

    def test_unknown_firmware_name_is_a_usage_error(self):
        import subprocess
        r = subprocess.run([os.path.join(HERE, 'firmware_build_ci.sh'), 'nonsense'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('usage:', (r.stdout + r.stderr).lower())

    def workflow(self, name):
        return open(os.path.join(HERE, '..', '.github', 'workflows', name)).read()

    def test_ci_builds_with_the_release_image(self):
        import re
        image = r'espressif/esp-matter:[\w.-]+@sha256:[0-9a-f]{64}'
        release = set(re.findall(image, self.workflow('release.yml')))
        self.assertEqual(len(release), 1)
        self.assertEqual(set(re.findall(image, self.workflow('ci.yml'))), release)

    def test_ci_check_waits_for_the_hub_build(self):
        import re
        job = re.search(r'^  ci:\n(.*?)(?=^  \S|\Z)', self.workflow('ci.yml'), re.M | re.S).group(1)
        needs = re.search(r'^    needs: \[([^\]]*)\]', job, re.M).group(1)
        self.assertIn('hub-build', [n.strip() for n in needs.split(',')])

    def test_ci_check_waits_for_the_controller_build(self):
        import re
        job = re.search(r'^  ci:\n(.*?)(?=^  \S|\Z)', self.workflow('ci.yml'), re.M | re.S).group(1)
        needs = re.search(r'^    needs: \[([^\]]*)\]', job, re.M).group(1)
        self.assertIn('controller-build', [n.strip() for n in needs.split(',')])

    def test_ci_builds_the_controller_like_a_release(self):
        script = open(os.path.join(HERE, 'firmware_build_ci.sh')).read()
        release = open(os.path.join(HERE, 'release_firmware.py')).read()
        for text in ('-DTILT_RELEASE=1', 'build-release', 'sdkconfig.release'):
            self.assertIn(text, script)
            self.assertIn(text, release)
        self.assertIn('controller)', script)

    def controller_filter(self):
        """The changes job's controller test, as a function of one path: (paths it drops, paths it keeps)."""
        import re
        line = next(l for l in self.workflow('ci.yml').splitlines() if 'grep -vE' in l and 'blinds_matter/test/' in l)
        drop, keep = re.findall(r"grep -[vq]E '([^']+)'", line)
        return lambda path: not re.search(drop, path) and bool(re.search(keep, path))

    def test_controller_build_runs_only_for_its_inputs(self):
        builds = self.controller_filter()
        for path in ('firmware/blinds_matter/main/hub_link.h', 'firmware/blinds_matter/CMakeLists.txt',
                     'firmware/blinds_matter/sdkconfig.defaults', 'tools/firmware_build_ci.sh', '.github/workflows/ci.yml'):
            self.assertTrue(builds(path), path)
        for path in ('firmware/blinds_matter/test/logic_test.cpp', 'app/x.swift', 'docs/x.md',
                     'firmware/tilt_hub/main/app_main.cpp'):
            self.assertFalse(builds(path), path)


class FirmwareSize(unittest.TestCase):
    """The app-slot headroom check CI runs after each firmware build (tools/firmware_size.py)."""

    def table(self, firmware):
        return open(os.path.join(HERE, '..', 'firmware', firmware, 'partitions.csv')).read()

    def test_hub_headroom_from_its_real_table(self):
        self.assertEqual(firmware_size.headroom(0x1df0e0, self.table('tilt_hub')), (0x1f0000, 69408))

    def test_controller_table_with_blank_offsets(self):
        self.assertEqual(firmware_size.headroom(0, self.table('blinds_matter'))[0], 0x1e0000)

    def test_smallest_app_slot_counts(self):
        table = 'nvs, data, nvs, 0x9000, 0x6000,\nota_0, app, ota_0, , 2M,\nota_1, app, ota_1, , 1536K,\n'
        self.assertEqual(firmware_size.headroom(1000000, table), (1536 * 1024, 1536 * 1024 - 1000000))

    def test_table_with_no_app_slot_is_an_error(self):
        with self.assertRaises(ValueError):
            firmware_size.headroom(10, 'nvs, data, nvs, 0x9000, 0x6000,\n')

    def run_cli(self, image_size):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            image = os.path.join(d, 'tilt_hub.bin')
            with open(image, 'wb') as f:
                f.truncate(image_size)
            table = os.path.join(HERE, '..', 'firmware', 'tilt_hub', 'partitions.csv')
            return subprocess.run([os.path.join(HERE, 'firmware_size.py'), image, table, '--floor', '32768'],
                                  capture_output=True, text=True)

    def test_cli_fails_one_byte_under_the_floor(self):
        r = self.run_cli(0x1f0000 - 32768 + 1)
        self.assertEqual(r.returncode, 1)
        self.assertIn('32767 bytes', r.stdout)

    def test_cli_passes_at_the_floor(self):
        r = self.run_cli(0x1f0000 - 32768)
        self.assertEqual(r.returncode, 0)
        self.assertIn('tilt_hub.bin: 0x1e8000 of 0x1f0000 used, 32768 bytes (32 KB) free, floor 32 KB', r.stdout)

    def test_ci_build_checks_the_size_of_both_firmwares(self):
        script = open(os.path.join(HERE, 'firmware_build_ci.sh')).read()
        self.assertIn('firmware_size.py', script)
        self.assertIn('--floor', script)
        for name in ('tilt_hub.bin', 'blinds_matter.bin'):
            self.assertIn(name, script)

class HubPeopleLock(unittest.TestCase):
    """The Tilt Hub reads its people under keyMx (firmware/tilt_hub/main/hub_pair.h). The lock is only on the chip,
    so these read the source."""
    MAIN = os.path.join(HERE, '..', 'firmware', 'tilt_hub', 'main')

    def source(self, name):
        with open(os.path.join(self.MAIN, name)) as f:
            return f.read()

    def hub_owned_body(self):
        import re
        m = re.search(r'^static bool hubOwned\(\) \{(.*?)^\}', self.source('hub_pair.h'), re.M | re.S)
        self.assertIsNotNone(m, 'hubOwned() not found in hub_pair.h')
        return m.group(1)

    def test_hub_owned_reads_the_people_under_the_lock(self):
        body = self.hub_owned_body()
        take = body.find('xSemaphoreTake(keyMx')
        read = body.find('people.owned()')
        give = body.find('xSemaphoreGive(keyMx')
        self.assertNotEqual(read, -1)
        self.assertTrue(-1 < take < read < give, body)

    def test_owned_is_read_only_through_hub_owned(self):
        body = self.hub_owned_body()
        for name in sorted(os.listdir(self.MAIN)):
            path = os.path.join(self.MAIN, name)
            if name == 'hub_people.h' or not os.path.isfile(path):
                continue
            text = self.source(name)
            if name == 'hub_pair.h':
                text = text.replace(body, '')
            self.assertNotIn('people.owned()', text, name + ': read "owned" through hubOwned(), which holds keyMx')

    def test_no_owned_call_while_holding_the_lock(self):
        import re
        lock = re.compile(r'xSemaphore(Take|Give)\(keyMx')
        call = re.compile(r'(?<!static bool )(?<!static void )\b(hubOwned|announceHub)\(\)')  # not its declaration
        calls = 0
        for name in ('hub_pair.h', 'hub_api.h', 'hub_matter.h'):
            text = self.source(name)
            for m in call.finditer(text):
                before = text[:m.start()]
                line = text.count('\n', 0, m.start()) + 1
                calls += 1
                last = list(lock.finditer(before))
                self.assertFalse(last and last[-1].group(1) == 'Take',
                                 '%s:%d calls %s() while holding keyMx (it takes keyMx: the hub would hang)'
                                 % (name, line, m.group(1)))
        self.assertGreaterEqual(calls, 6)        # helloJson, hInfo, announceHub's own read, three announceHub calls


if __name__ == '__main__':
    unittest.main()
