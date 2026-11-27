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
    EVERY = sorted(c for n in orient.PARTS for c in orient.copies(n))
    PLATES = bambu_project.BULK + bambu_project.SINGLE + bambu_project.CONTROLLER

    def test_every_part_has_its_own_plate(self):
        printed = [n for _, rows in bambu_project.SINGLE for r in rows for n in r]
        self.assertEqual(sorted(printed), self.EVERY)

    def test_every_project_has_studio_project_info(self):
        self.assertEqual(set(bambu_project.PROFILE), set(bambu_project.PROJECTS))
        for name in bambu_project.PROJECTS:
            info = bambu_project.project_info(name)
            for key in ('Title', 'Designer', 'Description', 'ProfileTitle', 'ProfileDescription'):
                self.assertTrue(info[key], (name, key))
        model = bambu_project.set_metadata('<metadata name="Title"></metadata>\n <resources>', {'Title': 'a & b',
                                                                                                  'Designer': 'x'})
        self.assertIn('<metadata name="Title">a &amp;amp; b</metadata>', model)
        self.assertIn('<metadata name="Designer">x</metadata>', model)

    def test_controller_box_is_its_own_project(self):
        self.assertEqual(sorted(n for _, rows in bambu_project.CONTROLLER[:1] for r in rows for n in r),
                         sorted(bambu_project.BOX))
        self.assertEqual([rows for _, rows in bambu_project.CONTROLLER[1:]], [[[n]] for n in bambu_project.BOX])

    def test_bulk_prints_one_tilter_one_material_per_plate(self):
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


def _has(*mods):
    import importlib.util
    return all(importlib.util.find_spec(m) for m in mods)


def dashed_manual(code):
    return code[:4] + '-' + code[4:7] + '-' + code[7:]


class DeviceIdentity(unittest.TestCase):
    """tools/device_identity.py: a hub's Apple Home code and setup code, made on the Mac at its first USB flash."""
    # The Matter SDK's public test code (connectedhomeip src/include/platform/CHIPDeviceConfig.h): passcode 20202021,
    # salt "SPAKE2P Key Salt", 1000 iterations, and the verifier "spake2p gen-verifier" made for them.
    SDK_SALT = b'SPAKE2P Key Salt'
    SDK_VERIFIER = ('uWFwqugDNGiEck/po7KHwwMwwqZgN10XuyBajPGuyzUEV/iree4lOrao5GuwnlQ65CJzbeUB49s31EH+NEkg0JVI5MGCQGMMT/SRPFNRODm3wH/'
                    'MBiehuFc6FJ/NH6Rmzw==')
    # What the SDK's src/setup_payload/python/SetupPayload.py gives (BLE, standard flow, vendor 0xFFF1, product 0x8000).
    SDK_CODES = [(3840, 20202021, '34970112332', 'MT:Y.K9042C00KA0648G00'),
                 (0, 1, '00000100007', 'MT:Y.K9042C00ID0000000'),
                 (0xABC, 51234567, '23456731273', 'MT:Y.K90-C7141FPH45310')]

    def setUp(self):
        import device_identity
        self.di = device_identity

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_verifier_matches_the_sdk_test_verifier(self):
        import base64
        self.assertEqual(self.di.verifier(20202021, self.SDK_SALT, 1000), base64.b64decode(self.SDK_VERIFIER))

    def test_manual_code_and_qr_text_match_the_sdk(self):
        for disc, pin, manual, qr in self.SDK_CODES:
            self.assertEqual(self.di.manual_code(disc, pin), manual)
            self.assertEqual(self.di.qr_payload(disc, pin, 0xFFF1, 0x8000), qr)
            self.assertTrue(self.di.verhoeff_ok(manual), manual)
        self.assertFalse(self.di.verhoeff_ok('34970112333'))

    # The same hex is in firmware/blinds_matter/test/logic_test.cpp, which reads it as a HomeCode.
    BLOB = ('0100434825423401e8030000000f000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f'
            'b96170aae803346884724fe9a3b287c30330c2a660375d17bb205a8cf1aecb350457f8ab79ee253ab6a8e46bb09e54'
            '3ae422736de501e3db37d441fe344920d09548e4c18240630c4ff4913c53513839b7c07fcc0627a1b8573a149fcd1fa4'
            '66cf00')

    def sdk_identity(self, **kw):
        import base64
        ident = {'passcode': 20202021, 'discriminator': 3840, 'iterations': 1000, 'salt': bytes(range(32)).hex(),
                 'verifier': base64.b64decode(self.SDK_VERIFIER).hex(), 'setup_code': '24681357'}
        ident.update(kw)
        return ident

    def test_home_code_blob_is_the_firmwares_struct(self):
        self.assertEqual(self.di.home_code_blob(self.sdk_identity()).hex(), self.BLOB)

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_new_identity_is_random_and_valid(self):
        made = [self.di.new_identity() for _ in range(200)]
        for m in made:
            self.assertTrue(self.di.pin_valid(m['passcode']))
            self.assertLess(m['discriminator'], 4096)
            self.assertEqual(len(bytes.fromhex(m['salt'])), 32)
            self.assertEqual(bytes.fromhex(m['verifier']), self.di.verifier(m['passcode'], bytes.fromhex(m['salt']), 1000))
            self.assertRegex(m['setup_code'], r'^\d{8}$')
            self.assertEqual(len(self.di.home_code_blob(m)), 144)
        self.assertEqual(len({m['passcode'] for m in made}), 200)
        self.assertEqual(len({m['salt'] for m in made}), 200)

    def test_nvs_csv_holds_only_the_two_codes(self):
        import csv, io
        rows = list(csv.reader(io.StringIO(self.di.nvs_csv(self.sdk_identity()))))
        self.assertEqual(rows[0], ['key', 'type', 'encoding', 'value'])
        self.assertEqual(rows[1], ['hub', 'namespace', '', ''])
        self.assertEqual(rows[2], ['homecode', 'data', 'hex2bin', self.BLOB])
        self.assertEqual(rows[3], ['pin', 'data', 'string', '24681357'])
        self.assertEqual(len(rows), 4)

    # A hub's saved data read back over USB: erased (all 0xFF), or holding the key "homecode" (16-byte NVS key field).
    EMPTY = b'\xff' * 0xC000
    WITH_CODE = b'\xff' * 100 + b'homecode' + b'\0' * 8 + b'\xff' * 100

    def test_plan_follows_the_table(self):
        rec = {'kind': 'hub', 'id': 'hub404ccaffee1234'}
        self.assertEqual(self.di.plan(None, self.EMPTY, False), 'new')           # nothing anywhere: a new identity
        self.assertEqual(self.di.plan(rec, self.EMPTY, False), 'restore')        # erased: the same one back
        self.assertEqual(self.di.plan(rec, self.WITH_CODE, False), 'firmware')   # firmware only
        self.assertEqual(self.di.plan(None, self.WITH_CODE, False), 'own')       # made its own: firmware only
        for r in (None, rec):
            for dump in (self.EMPTY, self.WITH_CODE):
                self.assertEqual(self.di.plan(r, dump, True), 'replace')

    def records(self):
        d = tempfile.mkdtemp()
        os.environ['TILT_DEVICES'] = os.path.join(d, 'devices')
        self.addCleanup(os.environ.pop, 'TILT_DEVICES', None)
        return os.environ['TILT_DEVICES']

    def test_records_are_private_and_found_by_full_or_short_id(self):
        d = self.records()
        self.di.save({'kind': 'hub', 'id': 'hub404ccaffee1234', 'short': '1234'})
        self.di.save({'kind': 'controller', 'id': '404ccaffab12', 'short': 'ab12'})
        self.assertEqual(os.stat(d).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.join(d, 'hub404ccaffee1234.json')).st_mode & 0o777, 0o600)
        self.assertEqual(self.di.find('hub404ccaffee1234')['short'], '1234')
        self.assertEqual(self.di.find('AB12')['id'], '404ccaffab12')
        self.assertEqual(self.di.load('nope'), None)
        with self.assertRaises(LookupError):
            self.di.find('9999')

    def test_two_devices_with_the_same_short_id_is_an_error_naming_both(self):
        self.records()
        self.di.save({'kind': 'hub', 'id': 'hub404ccaffee1234', 'short': '1234'})
        self.di.save({'kind': 'controller', 'id': '404ccaff1234', 'short': '1234'})
        with self.assertRaises(LookupError) as e:
            self.di.find('1234')
        self.assertIn('hub404ccaffee1234', str(e.exception))
        self.assertIn('404ccaff1234', str(e.exception))

    def test_record_folder_is_outside_the_repo_and_tools_devices_is_ignored(self):
        os.environ.pop('TILT_DEVICES', None)
        repo = os.path.realpath(os.path.join(HERE, '..'))
        self.assertFalse(os.path.realpath(self.di.devices_dir()).startswith(repo + os.sep))
        with open(os.path.join(repo, '.gitignore')) as f:
            self.assertIn('tools/devices/', f.read().split())

    def hub_record(self):
        ident = self.sdk_identity()
        return dict(ident, kind='hub', id='hub404ccaffee1234', short='1234', flashed='2026-11-26', firmware='0.3.19',
                    manual_code='34970112332', qr='MT:Y.K9042C00KA0648G00')

    @unittest.skipUnless(_has('qrcode', 'PIL'), 'needs qrcode and pillow')
    def test_hub_label_draws_the_qr_exactly(self):
        import qrcode
        from PIL import Image
        self.records()
        rec = self.hub_record()
        png, pdf = self.di.label(rec)
        self.assertEqual(os.path.dirname(png), self.di.devices_dir())
        img = Image.open(png).convert('L')
        self.assertEqual(img.size, (472, 236))                    # 40 x 20 mm at 300 dpi
        q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
        q.add_data(rec['qr'])
        q.make(fit=True)
        matrix = q.get_matrix()
        _, (x0, y0, px) = self.di.label_image(rec, (40, 20), 300)
        self.assertGreaterEqual(px, 3)
        for r, row in enumerate(matrix):
            for c, dark in enumerate(row):
                self.assertEqual(img.getpixel((x0 + c * px + px // 2, y0 + r * px + px // 2)) < 128, dark, (r, c))
        with open(pdf, 'rb') as f:
            body = f.read()
        self.assertTrue(body.startswith(b'%PDF'))
        import re
        box = [float(v) for v in re.search(rb'/MediaBox \[\s*([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)', body).groups()]
        self.assertAlmostEqual((box[2] - box[0]) * 25.4 / 72, 40, delta=0.1)
        self.assertAlmostEqual((box[3] - box[1]) * 25.4 / 72, 20, delta=0.1)
        self.assertEqual(os.stat(png).st_mode & 0o777, 0o600)

    @unittest.skipUnless(_has('qrcode', 'PIL'), 'needs qrcode and pillow')
    def test_label_too_small_for_the_qr_is_refused_with_the_smallest_size(self):
        self.records()
        with self.assertRaises(ValueError) as e:
            self.di.label(self.hub_record(), (10, 10))
        self.assertIn('17 x 9 mm', str(e.exception))
        self.assertEqual(self.di.parse_size('25x25'), (25.0, 25.0))
        with self.assertRaises(ValueError):
            self.di.parse_size('big')

    @unittest.skipUnless(_has('qrcode', 'PIL'), 'needs qrcode and pillow')
    def test_controller_label_has_no_qr(self):
        self.records()
        rec = {'kind': 'controller', 'id': '404ccaffab12', 'short': 'ab12', 'flashed': '2026-11-26', 'firmware': '2.4.0'}
        img, qr_box = self.di.label_image(rec, (40, 20), 300)
        self.assertIsNone(qr_box)
        self.assertEqual(img.size, (472, 236))

    class FakeDevice:
        """Stands in for esptool, the NVS image tool and build.sh: keeps what each command was, and the device's NVS."""
        def __init__(self, nvs):
            self.nvs, self.cmds, self.csvs, self.paths = nvs, [], [], []

        def __call__(self, cmd, cwd=None):
            line = ' '.join(cmd)
            self.paths += [a for a in cmd if 'tilt-nvs-' in a]             # the tool's own temp folder
            if 'read_mac' in cmd:
                self.cmds.append('read_mac')
                return 'Chip is ESP32-C6\nMAC: 40:4c:ca:ff:fe:ee:12:34\nBASE MAC: 40:4c:ca:ee:12:34\nMAC_EXT: ff:fe\n'
            if 'read_flash' in cmd:
                self.cmds.append('read_flash')
                with open(cmd[-1], 'wb') as f:
                    f.write(self.nvs)
            elif 'erase_region' in cmd:
                self.cmds.append('wipe')
                self.nvs = b'\xff' * 0xC000
            elif 'esp_idf_nvs_partition_gen' in line:
                with open(cmd[-3]) as f:
                    self.csvs.append(f.read())
                with open(cmd[-2], 'wb') as f:
                    f.write(b'image')
                self.cmds.append('nvs_image')
            elif 'write_flash' in cmd:
                self.cmds.append('write')
                self.nvs = b'homecode\0'
            elif cmd[0].endswith('build.sh'):
                self.cmds.append('flash' if 'flash' in cmd else 'build')
            return 'ok\n'

    def flash(self, kind, dev, **kw):
        import io
        fw = tempfile.mkdtemp()
        with open(os.path.join(fw, 'sdkconfig'), 'w') as f:
            f.write('CONFIG_DEVICE_VENDOR_ID=0xFFF1\nCONFIG_DEVICE_PRODUCT_ID=0x8000\n')
        with open(os.path.join(fw, 'partitions.csv'), 'w') as f:
            f.write('# Name, Type, SubType, Offset, Size\nnvs,      data, nvs,     0x10000,   0xC000,\n')
        out = io.StringIO()
        code = self.di.flash(kind, '/dev/cu.test', run=dev, out=out, fw_dir=fw, **kw)
        return code, out.getvalue()

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_flash_a_fresh_hub_saves_a_private_record_and_prints_no_code(self):
        d = self.records()
        dev = self.FakeDevice(self.EMPTY)
        code, out = self.flash('hub', dev)
        self.assertEqual(code, 0)
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'nvs_image', 'write', 'flash'])
        path = os.path.join(d, 'hub404ccaee1234.json')
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        rec = self.di.load('hub404ccaee1234')
        self.assertEqual((rec['kind'], rec['short']), ('hub', '1234'))
        self.assertEqual(rec['manual_code'], self.di.manual_code(rec['discriminator'], rec['passcode']))
        self.assertEqual(rec['qr'], self.di.qr_payload(rec['discriminator'], rec['passcode'], 0xFFF1, 0x8000))
        for p in dev.paths:
            self.assertFalse(os.path.exists(p), p + ' left behind')
        self.assertTrue(dev.paths)
        for secret in (str(rec['passcode']), rec['manual_code'], dashed_manual(rec['manual_code']), rec['qr'],
                       rec['setup_code'], rec['setup_code'][:4] + '-' + rec['setup_code'][4:]):
            self.assertNotIn(secret, out)
            self.assertNotIn(secret, ' '.join(dev.cmds))

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_erased_hub_gets_the_same_code_back(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        self.flash('hub', dev)
        dev.nvs, dev.cmds = self.EMPTY, []
        self.assertEqual(self.flash('hub', dev)[0], 0)
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'nvs_image', 'write', 'flash'])
        self.assertEqual(dev.csvs[0], dev.csvs[1])            # the same homecode and pin, byte for byte

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_hub_with_a_code_gets_firmware_only(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        self.flash('hub', dev)
        before = self.di.load('hub404ccaee1234')
        dev.cmds = []
        self.assertEqual(self.flash('hub', dev)[0], 0)                       # record and code: firmware only
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'flash'])
        self.assertEqual(self.di.load('hub404ccaee1234'), before)
        self.records()
        dev = self.FakeDevice(self.WITH_CODE)
        code, out = self.flash('hub', dev)                                   # its own code, no record here
        self.assertEqual((code, dev.cmds), (0, ['read_mac', 'read_flash', 'build', 'flash']))
        self.assertIn('made its own', out)
        self.assertEqual(self.di.records(), [])

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_new_identity_asks_for_the_short_id(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        self.flash('hub', dev)
        first = self.di.load('hub404ccaee1234')
        dev.cmds = []
        self.assertEqual(self.flash('hub', dev, new_identity=True, ask=None)[0], 1)    # no terminal: refused
        self.assertEqual(dev.cmds, [])
        self.assertEqual(self.flash('hub', dev, new_identity=True, ask=lambda p: '9999')[0], 1)
        self.assertEqual(dev.cmds, ['read_mac'])                                      # nothing changed
        self.assertEqual(self.di.load('hub404ccaee1234'), first)
        dev.cmds = []
        self.assertEqual(self.flash('hub', dev, new_identity=True, ask=lambda p: '1234')[0], 0)
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'wipe', 'nvs_image', 'write', 'flash'])
        self.assertNotEqual(self.di.load('hub404ccaee1234')['salt'], first['salt'])
        old = [n for n in os.listdir(self.di.devices_dir()) if '.replaced-' in n]
        self.assertEqual(len(old), 1)
        import json
        with open(os.path.join(self.di.devices_dir(), old[0])) as f:
            self.assertEqual(json.load(f)['salt'], first['salt'])
        self.assertEqual([r['id'] for r in self.di.records()], ['hub404ccaee1234'])

    def test_controller_gets_a_record_and_no_new_identity(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        self.assertEqual(self.flash('controller', dev)[0], 0)
        self.assertEqual(dev.cmds, ['read_mac', 'build', 'flash'])
        rec = self.di.load('404ccaee1234')
        self.assertEqual((rec['kind'], rec['short']), ('controller', '1234'))
        self.assertNotIn('passcode', rec)
        dev.cmds = []
        self.assertEqual(self.flash('controller', dev, new_identity=True, ask=lambda p: '1234')[0], 1)
        self.assertEqual(dev.cmds, [])

    @unittest.skipUnless(_has('qrcode', 'PIL', 'cryptography'), 'needs qrcode, pillow and cryptography')
    def test_labels_command_writes_the_same_png_as_the_flash(self):
        self.records()
        self.flash('hub', self.FakeDevice(self.EMPTY))
        png = os.path.join(self.di.devices_dir(), 'hub404ccaee1234.png')
        with open(png, 'rb') as f:
            first = f.read()
        os.remove(png)
        self.assertEqual(self.di.main(['labels', '1234']), 0)
        with open(png, 'rb') as f:
            self.assertEqual(f.read(), first)
        self.assertEqual(self.di.main(['labels', '--all', '--label-size', '50x25']), 0)
        self.assertEqual(self.di.main(['labels', '9999']), 1)

    def test_flash_scripts_help_mentions_usb_and_the_developer_flag(self):
        import subprocess
        for script in ('flash.sh', 'flash_hub.sh'):
            r = subprocess.run(['bash', os.path.join(HERE, script), '--help'], capture_output=True, text=True,
                               env=dict(os.environ, PY='/nonexistent'))
            self.assertEqual(r.returncode, 0, script)
            self.assertIn('--usb', r.stdout)
            self.assertIn('--new-identity', r.stdout)
            self.assertNotIn('building', r.stdout)

    def test_hub_factory_reset_keeps_both_codes_on_the_label(self):
        import re
        with open(os.path.join(HERE, '..', 'firmware', 'tilt_hub', 'main', 'hub.cpp')) as f:
            text = f.read()
        reset = text[text.index('static void resetTask'):text.index('extern "C" void app_main')]
        after_erase = reset[reset.index('nvs_flash_erase()'):]
        self.assertRegex(after_erase, r'nvs_set_blob\(nv, "homecode"')
        self.assertRegex(after_erase, r'nvs_set_str\(nv, "pin"')

    def test_passcode_rule_is_the_firmwares(self):
        for ok in (1, 99999998, 24681357):
            self.assertTrue(self.di.pin_valid(ok), ok)
        for bad in (0, 99999999, 33333333, 11111111, 12345678, 87654321, 100000000):
            self.assertFalse(self.di.pin_valid(bad), bad)


if __name__ == '__main__':
    unittest.main()
