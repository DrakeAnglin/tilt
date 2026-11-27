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
import coverage_gate  # noqa: E402
import firmware_size  # noqa: E402
import inventory  # noqa: E402
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
        # A run that made a code did not finish: what the hub holds now decides.
        pending = dict(self.sdk_identity(), kind='hub', id='hub404ccaffee1234', pending=True)
        ours = b'\xff' * 64 + b'homecode\0' + self.di.home_code_blob(pending) + b'\xff' * 64
        self.assertEqual(self.di.plan(pending, self.EMPTY, False), 'resume')             # no code: write it
        self.assertEqual(self.di.plan(pending, ours, False), 'finish')                   # has it: firmware only
        self.assertEqual(self.di.plan(pending, self.WITH_CODE, False), 'resume_replace')  # another: ask first

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
        q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
        q.add_data(rec['qr'])
        q.make(fit=True)
        matrix = q.get_matrix()
        # The default: a 1 x 1 in (25 x 25 mm) square at 300 dpi, the issue's size. And a wide one.
        for size_mm, px_size in (((25, 25), (295, 295)), ((40, 20), (472, 236))):
            png, pdf = self.di.label(rec) if size_mm == (25, 25) else self.di.label(rec, size_mm)
            self.assertEqual(os.path.dirname(png), self.di.devices_dir())
            img = Image.open(png).convert('L')
            self.assertEqual(img.size, px_size)
            _, (x0, y0, px) = self.di.label_image(rec, size_mm, 300)
            self.assertGreaterEqual(px, 3)
            for r, row in enumerate(matrix):
                for c, dark in enumerate(row):
                    self.assertEqual(img.getpixel((x0 + c * px + px // 2, y0 + r * px + px // 2)) < 128, dark, (r, c))
            with open(pdf, 'rb') as f:
                body = f.read()
            self.assertTrue(body.startswith(b'%PDF'))
            import re
            box = [float(v) for v in re.search(rb'/MediaBox \[\s*([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)', body).groups()]
            self.assertAlmostEqual((box[2] - box[0]) * 25.4 / 72, size_mm[0], delta=0.1)
            self.assertAlmostEqual((box[3] - box[1]) * 25.4 / 72, size_mm[1], delta=0.1)
            self.assertEqual(os.stat(png).st_mode & 0o777, 0o600)
        self.assertEqual(self.di.DEFAULT_SIZE, (25.0, 25.0))

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
        img, qr_box = self.di.label_image(rec)
        self.assertIsNone(qr_box)
        self.assertEqual(img.size, (295, 295))

    class FakeDevice:
        """Stands in for esptool, the NVS image tool and build.sh: keeps what each command was, and the device's NVS."""
        def __init__(self, nvs):
            self.nvs, self.cmds, self.csvs, self.paths, self.fail = nvs, [], [], [], None

        def __call__(self, cmd, cwd=None):
            line = ' '.join(cmd)
            step = ('wipe' if 'erase_region' in cmd else 'write' if 'write_flash' in cmd else
                    'nvs_image' if 'esp_idf_nvs_partition_gen' in line else
                    'flash' if cmd[0].endswith('build.sh') and 'flash' in cmd else None)
            if step and step == self.fail:
                self.cmds.append(step + ' failed')
                raise RuntimeError('%s failed: the cable came out' % step)
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
                blob = self.csvs[-1].split('homecode,data,hex2bin,')[1].split(',')[0].split('\n')[0]
                self.nvs = b'homecode\0' + bytes.fromhex(blob)        # NVS keeps a blob's bytes in a row
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
    def test_a_failed_step_never_loses_a_new_code(self):
        for fail in ('nvs_image', 'write', 'flash'):
            self.records()
            dev = self.FakeDevice(self.EMPTY)
            dev.fail = fail
            code, out = self.flash('hub', dev)
            self.assertEqual(code, 1, fail)
            self.assertIn('Unplug', out)
            rec = self.di.load('hub404ccaee1234')                     # saved before anything was written
            self.assertTrue(rec['pending'], fail)
            dev.fail, dev.cmds = None, []
            self.assertEqual(self.flash('hub', dev)[0], 0)              # the rerun finishes it with the same code
            if fail == 'flash':                                        # the code was already on the hub: no write
                self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'flash'])
            else:                                                      # nothing on it yet: written, never wiped
                self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'nvs_image', 'write', 'flash'])
            done = self.di.load('hub404ccaee1234')
            self.assertNotIn('pending', done)
            self.assertEqual(done['salt'], rec['salt'])
            self.assertIn(self.di.home_code_blob(done), dev.nvs)

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_a_failed_new_identity_keeps_the_new_code_and_the_old_record(self):
        for fail in ('wipe', 'write', 'flash'):
            self.records()
            dev = self.FakeDevice(self.EMPTY)
            self.flash('hub', dev)
            first = self.di.load('hub404ccaee1234')
            dev.fail, dev.cmds = fail, []
            code, out = self.flash('hub', dev, new_identity=True, ask=lambda p: '1234')
            self.assertEqual(code, 1, fail)
            self.assertIn('run the same command again', out)
            new = self.di.load('hub404ccaee1234')
            self.assertTrue(new['pending'])
            self.assertNotEqual(new['salt'], first['salt'])
            old = [n for n in os.listdir(self.di.devices_dir()) if '.replaced-' in n]
            self.assertEqual(len(old), 1)
            dev.fail = None
            # A wipe that failed leaves the old code on the hub: the rerun asks before it wipes.
            code, out = self.flash('hub', dev, ask=lambda p: '1234')
            self.assertEqual(code, 0)
            self.assertEqual(self.di.load('hub404ccaee1234')['salt'], new['salt'])
            self.assertIn(self.di.home_code_blob(new), dev.nvs)
            self.assertNotIn('Warning', out)

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_unfinished_run_never_wipes_a_hub_with_another_code_without_asking(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        dev.fail = 'nvs_image'
        self.flash('hub', dev)                                         # leaves a pending record, nothing on the hub
        pending = self.di.load('hub404ccaee1234')
        dev.fail, dev.nvs = None, self.WITH_CODE + b'thread and owners'  # since then set up another way, in a home
        for ask in (None, lambda p: '9999'):                            # no terminal, or the wrong short ID
            dev.cmds = []
            code, out = self.flash('hub', dev, ask=ask)
            self.assertEqual(code, 1)
            self.assertEqual(dev.cmds, ['read_mac', 'read_flash'])       # no build, no wipe, no write
            self.assertTrue(dev.nvs.endswith(b'thread and owners'))
            self.assertNotIn('run the same command again', out)
            self.assertEqual(self.di.load('hub404ccaee1234'), pending)
        dev.cmds = []
        self.assertEqual(self.flash('hub', dev, ask=lambda p: '1234')[0], 0)
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'wipe', 'nvs_image', 'write', 'flash'])
        self.assertIn(self.di.home_code_blob(pending), dev.nvs)
        self.assertNotIn('pending', self.di.load('hub404ccaee1234'))

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_unfinished_run_with_the_code_already_on_the_hub_only_flashes(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        dev.fail = 'flash'
        self.flash('hub', dev)
        dev.nvs += b'thread and owners'                                # finished another way, now in a home
        dev.fail, dev.cmds = None, []
        code, out = self.flash('hub', dev, ask=None)
        self.assertEqual(code, 0)
        self.assertEqual(dev.cmds, ['read_mac', 'read_flash', 'build', 'flash'])
        self.assertTrue(dev.nvs.endswith(b'thread and owners'))
        self.assertNotIn('pending', self.di.load('hub404ccaee1234'))

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_firmware_only_warns_when_the_hub_has_another_code(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        self.flash('hub', dev)
        dev.nvs = self.WITH_CODE                                       # set up from another Mac, say
        code, out = self.flash('hub', dev)
        self.assertEqual(code, 0)
        self.assertIn('not the one saved on this Mac', out)

    @unittest.skipUnless(_has('qrcode', 'PIL'), 'needs qrcode and pillow')
    def test_label_size_is_checked_before_the_device_is_touched(self):
        self.records()
        dev = self.FakeDevice(self.EMPTY)
        code, out = self.flash('hub', dev, size_mm=(10, 10))
        self.assertEqual((code, dev.cmds), (1, []))
        self.assertIn('17 x 9 mm', out)

    @unittest.skipUnless(_has('cryptography'), 'needs cryptography')
    def test_without_the_label_libraries_the_flash_still_saves_and_says_what_to_run(self):
        import io, sys as _sys
        from unittest import mock
        self.records()
        with mock.patch.dict(_sys.modules, {'PIL': None, 'qrcode': None}):
            code, out = self.flash('hub', self.FakeDevice(self.EMPTY))
            self.assertEqual(code, 0)
            self.assertTrue(self.di.load('hub404ccaee1234'))
            self.assertIn(_sys.executable + ' -m pip install pillow qrcode', out)
            self.assertIn('%s %s labels 1234' % (_sys.executable, self.di.__file__), out)
            buf = io.StringIO()
            with mock.patch('sys.stdout', buf):
                self.assertEqual(self.di.main(['labels', '1234']), 1)       # no traceback
            self.assertIn('pip install pillow qrcode', buf.getvalue())

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


def lcov(path, hits):
    """A made-up LCOV record: hits = {line: count}."""
    return 'SF:%s\n%s\nend_of_record\n' % (path, '\n'.join('DA:%d,%d' % (n, h) for n, h in sorted(hits.items())))


def added(path, start, count):
    """A made-up `git diff -U0` that adds `count` lines at `start`."""
    return 'diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -0,0 +%d,%d @@\n' % (path, path, path, path, start, count)


FAKE_GH_COMMENTS = r'''#!/usr/bin/env python3
import json, os, sys
state = os.environ["FAKE_GH_STATE"]
d = json.load(open(state))
a = sys.argv[1:]
d["calls"].append({"args": a, "stdin": sys.stdin.read() if "--input" in a else ""})
json.dump(d, open(state, "w"))
if "--paginate" in a:
    half = len(d["comments"]) // 2
    print(json.dumps(d["comments"][:half]) + json.dumps(d["comments"][half:]))
'''


class CoverageGate(unittest.TestCase):
    """tools/coverage_gate.py: the 90% changed-lines gate, the floors, the exclusion lists, the comment."""
    G = coverage_gate
    F = 'tools/thing.py'

    def run_gate(self, covered, total=10, changed=None, floor=0):
        src = {self.F: 'x = 1\n' * total}
        cov = self.G.parse_lcov(lcov(self.F, {n: (1 if n <= covered else 0) for n in range(1, total + 1)}))
        return self.G.measure('tools', src, cov, self.G.diff_lines(changed if changed is not None else added(self.F, 1, total)),
                              floor=floor)

    def test_nine_of_ten_changed_lines_pass(self):
        r = self.run_gate(9)
        self.assertTrue(r['ok'], r)
        self.assertEqual((r['changed_covered'], r['changed_total']), (9, 10))
        self.assertEqual(r['uncovered'], ['tools/thing.py:10'])

    def test_eight_of_ten_fail_and_list_the_lines(self):
        r = self.run_gate(8)
        self.assertFalse(r['ok'])
        self.assertEqual(r['uncovered'], ['tools/thing.py:9', 'tools/thing.py:10'])
        self.assertIn('under the 90% gate', ' '.join(r['notes']))

    def test_a_file_no_test_compiles_fails_on_its_code_lines(self):
        path = 'firmware/blinds_matter/main/new.h'
        text = '// a comment\n#pragma once\n\nint f() {\n  /* a\n     block */\n  return 1; // why\n}\n'
        r = self.G.measure('controller', {path: text}, {}, self.G.diff_lines(added(path, 1, 8)))
        self.assertFalse(r['ok'])
        self.assertEqual(r['uncovered'], ['%s:%d' % (path, n) for n in (2, 4, 7, 8)])
        self.assertEqual((r['covered'], r['total']), (0, 4))

    def test_code_lines_of_python_and_swift(self):
        self.assertEqual(self.G.code_lines('a.py', '# c\n\nx = 1\n  # d\n'), {3})
        self.assertEqual(self.G.code_lines('a.swift', '/* one */ let a = 1\n/* two */\nlet b = 2 /* x */\n'), {1, 3})

    def test_only_docs_tests_or_an_excluded_file_pass_with_no_changed_lines(self):
        src = {self.F: 'x = 1\n' * 4, 'tools/fusion_x.py': 'import adsk\n'}
        cov = self.G.parse_lcov(lcov(self.F, {1: 1, 2: 1, 3: 1, 4: 1}))
        diff = added('README.md', 1, 3) + added('tools/test_tools.py', 5, 2) + added('tools/fusion_x.py', 1, 1)
        r = self.G.measure('tools', src, cov, self.G.diff_lines(diff), excluded={'tools/fusion_x.py'})
        self.assertTrue(r['ok'], r)
        self.assertIsNone(r['changed'])
        self.assertIn('no changed lines', r['notes'])

    def test_the_floor(self):
        src = {self.F: 'x = 1\n' * 1000}
        cov = self.G.parse_lcov(lcov(self.F, {n: (1 if n <= 614 else 0) for n in range(1, 1001)}))
        r = self.G.measure('tools', src, cov, None, floor=61)
        self.assertTrue(r['ok'], r)
        self.assertAlmostEqual(r['overall'], 61.4)
        r = self.G.measure('tools', src, cov, None, floor=62)
        self.assertFalse(r['ok'])
        self.assertIn('under the floor of 62% by 0.6 points', ' '.join(r['notes']))
        r = self.G.measure('tools', src, cov, None, floor=59)
        self.assertIn('floor can go up to 61', ' '.join(r['notes']))

    def test_a_tracked_file_missing_from_the_lcov_counts_as_uncovered(self):
        src = {self.F: 'x = 1\n' * 4, 'tools/other.py': 'a = 1\nb = 2\n# no\n\nc = 3\nd = 4\n'}
        cov = self.G.parse_lcov(lcov(self.F, {1: 1, 2: 1, 3: 1, 4: 1}))
        r = self.G.measure('tools', src, cov)
        self.assertEqual((r['covered'], r['total']), (4, 8))
        self.assertAlmostEqual(r['overall'], 50.0)

    def test_records_of_one_file_add_up_and_paths_become_repo_paths(self):
        root = os.path.realpath(tempfile.mkdtemp())
        text = lcov(os.path.join(root, 'tools/a.py'), {1: 0, 2: 1}) + lcov(os.path.join(root, 'tools/a.py'), {1: 2}) + \
            lcov('/elsewhere/b.h', {1: 1}) + lcov('tools/c.py', {3: 0})
        self.assertEqual(self.G.parse_lcov(text, root), {'tools/a.py': {1: 2, 2: 1}, 'tools/c.py': {3: 0}})

    def test_paths_from_another_checkout_land_on_this_repo(self):
        # The app's coverage is made on a Mac runner (/Users/runner/...) and read on Linux (/home/runner/...).
        text = lcov('/Users/runner/work/tilt/tilt/tools/coverage_gate.py', {1: 1}) + lcov('/Users/runner/work/x/nothere.py', {1: 1})
        self.assertEqual(self.G.parse_lcov(text), {'tools/coverage_gate.py': {1: 1}})

    def test_exclusion_lines_need_a_reason_and_a_file(self):
        files = ['tools/fusion_a.py', 'tools/fusion_b.py', 'tools/bambu.py']
        excluded, errors = self.G.parse_exclusions('# the list\nfusion_*.py  # runs only inside Fusion\n', 'tools/coverage-exclude.txt', files)
        self.assertEqual((excluded, errors), ({'tools/fusion_a.py', 'tools/fusion_b.py'}, []))
        _, errors = self.G.parse_exclusions('bambu.py\n', 'tools/coverage-exclude.txt', files)
        self.assertIn('no reason', errors[0])
        _, errors = self.G.parse_exclusions('gone.py  # was here\n', 'tools/coverage-exclude.txt', files)
        self.assertIn('matches no file', errors[0])
        r = self.G.measure('tools', {'tools/bambu.py': 'x = 1\n'}, {}, errors=errors)
        self.assertFalse(r['ok'])

    def test_an_excluded_file_is_left_out_of_both_numbers(self):
        src = {self.F: 'x = 1\n' * 2, 'tools/fusion_a.py': 'a = 1\n' * 50}
        cov = self.G.parse_lcov(lcov(self.F, {1: 1, 2: 1}))
        r = self.G.measure('tools', src, cov, self.G.diff_lines(added('tools/fusion_a.py', 1, 50)), excluded={'tools/fusion_a.py'})
        self.assertEqual((r['covered'], r['total'], r['changed_total']), (2, 2, 0))
        self.assertTrue(r['ok'])

    def test_every_exclusion_list_in_the_repo_holds(self):
        for area in self.G.AREAS:
            sources, excluded, errors = self.G.area_inputs(area)
            self.assertEqual(errors, [], area)
            self.assertTrue(excluded <= set(sources), area)

    def test_the_areas_do_not_overlap_and_hold_no_test_file(self):
        files = self.G.repo_files()
        for f in files:
            hits = [a for a, (_, pattern, _) in self.G.AREAS.items() if __import__('re').fullmatch(pattern, f)]
            self.assertLessEqual(len(hits), 1, f)
            if hits:
                self.assertFalse(os.path.basename(f).startswith('test_') or '/Tests/' in f or '/test/' in f, f)
        for area in self.G.AREAS:
            self.assertTrue(any(self.G.area_of(f) == area for f in files), area)
        self.assertIsNone(self.G.area_of('app/Tilt/Tests/main.swift'))
        self.assertIsNone(self.G.area_of('tools/agent/test_agent.py'))
        self.assertEqual(self.G.area_of('tools/agent/claim.py'), 'tools')

    def test_no_inline_skip_markers_in_our_code(self):
        markers = ('pragma: ' + 'no cover', 'LCOV_' + 'EXCL', 'GCOV_' + 'EXCL')
        for f in self.G.repo_files():
            if self.G.area_of(f):
                text = self.G.read(f)
                for m in markers:
                    self.assertNotIn(m, text, f)

    def test_unused_inline_and_static_functions_are_uncovered(self):
        # The reason for clang's coverage: gcov style counts a function no test calls as "no code".
        import shutil, subprocess
        llvm_cov = shutil.which('llvm-cov') or (subprocess.run(['xcrun', '-f', 'llvm-cov'], capture_output=True).returncode == 0
                                                if shutil.which('xcrun') else None) or __import__('glob').glob('/usr/bin/llvm-cov-*')
        if not shutil.which('clang++') or not llvm_cov:
            self.skipTest('needs clang++ and llvm-cov (CI has both)')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = os.path.realpath(tmp)
            with open(os.path.join(tmp, 'fx.h'), 'w') as f:
                f.write('#pragma once\ninline int used(int x) {\n  return x + 1;\n}\ninline int unusedInline(int x) {\n'
                        '  return x * 2;\n}\nstatic int unusedStatic(int x) {\n  return x - 3;\n}\n')
            with open(os.path.join(tmp, 'fx_test.cpp'), 'w') as f:
                f.write('#include <cstdio>\n#include "fx.h"\nint main() { std::printf("%d passed, 0 failed\\n", used(0)); }\n')
            script = os.path.join(tmp, 'tests.sh')
            with open(script, 'w') as f:
                f.write('#!/bin/sh\nset -e\ncd "%s"\nOUT=$(mktemp -d)\nc++ -std=c++17 -o "$OUT/fx_test" fx_test.cpp\n'
                        '"$OUT/fx_test"\nrm -rf "$OUT"\n' % tmp)
            os.chmod(script, 0o755)
            out = os.path.join(tmp, 'out')
            r = subprocess.run([os.path.join(HERE, 'coverage.sh'), 'firmware', out], capture_output=True, text=True,
                               env=dict(os.environ, TILT_COVERAGE_TESTS=script))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(out, 'firmware.lcov')) as f:
                cov = self.G.parse_lcov(f.read(), tmp)['fx.h']
            with open(os.path.join(out, 'firmware.log')) as f:
                self.assertEqual(self.G.test_counts(f.read()), (1, 0))
        self.assertGreater(cov[3], 0)
        self.assertEqual(cov.get(6), 0, cov)
        self.assertEqual(cov.get(9), 0, cov)

    def test_test_counts(self):
        self.assertEqual(self.G.test_counts('12 passed, 0 failed\nota: 12 passed, 0 failed\niPhone: 3 passed, 1 failed\n'), (27, 1))
        log = '....\n------\nRan 40 tests in 1.2s\n\nFAILED (failures=2, errors=1)\nRan 1 test in 0.1s\n\nOK\n'
        self.assertEqual(self.G.test_counts(log), (38, 3))

    def results(self):
        r = self.run_gate(8)
        r['overall'] = 80.0
        return {'tools': r, 'controller': self.G.measure('controller', {}, {}, None)}

    def test_the_comment(self):
        body = self.G.render(self.results(), {'app': 'no app files changed'}, 'abc123', 'https://run/1',
                             {'tools': dict(self.results()['tools'], overall=78.5)})
        self.assertTrue(body.startswith(self.G.MARKER))
        rows = [line for line in body.splitlines() if line.startswith('| ') and not line.startswith('| Area')]
        self.assertEqual([row.split(' | ')[0][2:] for row in rows], ['Tilt app', 'controller firmware', 'Tilt Hub firmware', 'tools'])
        self.assertIn('did not run: no app files changed', rows[0])
        self.assertIn('not gated (main)', rows[1])
        self.assertIn('**fail**: no result', rows[2])
        self.assertIn('+1.5 points', rows[3])
        self.assertIn('80.0% (8 of 10)', rows[3])
        self.assertIn('`tools/thing.py:9`', body)
        self.assertIn('abc123', body.splitlines()[-1])
        self.assertIn('https://run/1', body.splitlines()[-1])
        self.assertEqual(self.G.failing(self.results(), {'app': 'x'}), ['hub', 'tools'])

    def post(self, comments):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            gh, state = os.path.join(tmp, 'gh'), os.path.join(tmp, 'state.json')
            with open(gh, 'w') as f:
                f.write(FAKE_GH_COMMENTS)
            os.chmod(gh, 0o755)
            with open(state, 'w') as f:
                json.dump({'comments': comments, 'calls': []}, f)
            old = os.environ.get('FAKE_GH_STATE')
            os.environ['FAKE_GH_STATE'] = state
            try:
                what = self.G.post('the body', 'o/r', 7, gh=gh)
            finally:
                os.environ.pop('FAKE_GH_STATE') if old is None else os.environ.update(FAKE_GH_STATE=old)
            with open(state) as f:
                return what, json.load(f)['calls'][1:]

    def test_the_first_post_makes_the_comment(self):
        what, calls = self.post([{'id': 1, 'user': {'login': 'someone'}, 'body': 'hello'}])
        self.assertEqual(what, 'made')
        self.assertEqual(calls[0]['args'][:4], ['api', '-X', 'POST', 'repos/o/r/issues/7/comments'])
        self.assertIn('the body', calls[0]['stdin'])

    def test_a_later_post_edits_the_bots_comment(self):
        what, calls = self.post([{'id': 1, 'user': {'login': 'someone'}, 'body': self.G.MARKER + ' fake'},
                                 {'id': 2, 'user': {'login': 'x'}, 'body': 'hi'},
                                 {'id': 3, 'user': {'login': 'github-actions[bot]'}, 'body': self.G.MARKER + ' old'}])
        self.assertEqual(what, 'edited')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['args'][:4], ['api', '-X', 'PATCH', 'repos/o/r/issues/comments/3'])

    def test_a_marker_from_someone_else_is_ignored(self):
        what, calls = self.post([{'id': 1, 'user': {'login': 'someone'}, 'body': self.G.MARKER}])
        self.assertEqual(what, 'made')
        self.assertEqual(calls[0]['args'][2], 'POST')

    def test_the_readme_table_matches_the_floors(self):
        floors = self.G.read_floors(self.G.read(self.G.FLOORS))
        self.assertEqual(sorted(floors), sorted(self.G.AREAS))
        text = self.G.read('README.md')
        self.assertEqual(self.G.rewrite_readme(text, floors), text, 'run tools/coverage_gate.py readme')
        self.assertIn('| Tilt Hub firmware | at least %d%% |' % floors['hub'], text)
        self.assertEqual(self.G.main(['readme', '--check']), 0)

    def test_check_and_comment_from_the_command_line(self):
        import io, contextlib, json
        with tempfile.TemporaryDirectory() as tmp:
            cov_file, log, out = os.path.join(tmp, 'tools.lcov'), os.path.join(tmp, 'tools.log'), os.path.join(tmp, 'r')
            with open(cov_file, 'w') as f:
                f.write(lcov(os.path.join(self.G.ROOT, 'tools/coverage_gate.py'), {n: 1 for n in range(1, 400)}))
            with open(log, 'w') as f:
                f.write('Ran 3 tests in 0.1s\n\nOK\n')
            with contextlib.redirect_stdout(io.StringIO()) as said:
                code = self.G.main(['check', '--area', 'tools', '--lcov', cov_file, '--log', log, '--out', out])
            self.assertIn('tests 3 passed, 0 failed', said.getvalue())
            with open(os.path.join(out, 'tools.json')) as f:
                r = json.load(f)
            self.assertEqual(code, 0 if r['ok'] else 1)
            self.assertFalse(r['gated'])
            with open(os.path.join(out, 'tools-files.txt')) as f:
                self.assertIn('tools/coverage_gate.py', f.read())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.G.main(['check', '--area', 'app', '--lcov', os.path.join(tmp, 'none'), '--base', 'HEAD']), 1)
            summary = os.path.join(tmp, 'summary.md')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                code = self.G.main(['comment', '--results', out, '--head', 'abc', '--run-url', 'u', '--main', tmp,
                                    '--skip', 'app=no app files changed', '--summary', summary])
            self.assertEqual(code, 1)
            self.assertIn('controller firmware', err.getvalue())
            with open(summary) as f:
                self.assertIn(self.G.MARKER, f.read())

    def test_changed_lines_since_a_commit(self):
        changed = self.G.changed_since('HEAD')
        self.assertIsInstance(changed, dict)
        self.assertEqual(self.G.diff_lines('+++ /dev/null\n@@ -1,3 +0,0 @@\n+++ b/a.py\n@@ -2 +2 @@\n@@ -9,2 +8,0 @@\n'),
                         {'a.py': {2}})


class Inventory(unittest.TestCase):
    """tools/inventory.py: the inventory skill's order list, worked out from the real BOM."""
    BOM = """# Bill of materials
## One tilter
### Printed
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| Housing | 1 | | [build](mechanical/stl/tilter/README.md) |
### Electronics
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| Motor; see [speed](#motor-speed) | 1 | 3-pack | [A1](https://www.amazon.com/dp/MOTOR1) |
| Wire | about 40 cm | kit ([Buy once](#buy-once)) | [W](https://www.amazon.com/dp/WIRE1) |
### Hardware
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| M3 × 20 screw | 4 (2 case, 2 tray) | in the M3 kit ([Buy once](#buy-once)) | [K](https://www.amazon.com/dp/KIT1) |
| M3 × 8 screw | 1 (lid corner) | in the M3 kit | [K](https://www.amazon.com/dp/KIT1) |
| Insert | 6 | pack of 100 | [I](https://www.amazon.com/dp/INS1) |
### Cord to the controller
| Part | Per tilter | Sold as | Link |
|---|---|---|---|
| Cord, 3.3 ft | 1 | 2-pack | [C3](https://www.amazon.com/dp/CORD3) |
| Cord, 6.6 ft | 1 | 2-pack | [C6](https://www.amazon.com/dp/CORD6) |
| Cord, 10 ft | 1 | 2-pack | [C10](https://www.amazon.com/dp/CORD10) |
## One controller
### Parts on the PCB
| Part | Exact part (or equivalent) | Per board | Sold as | Link |
|---|---|---|---|---|
| Jack | Amphenol **87180-066LF** | 1 per port you use (J9–J11, up to 3) | each | [DigiKey](https://www.digikey.com/x?k=87180) |
| Electrolytic | Panasonic EEU-FR1A471 | 1 (C9) | each | [DigiKey](https://www.digikey.com/x?k=EEU) |
| Resistors | 1 MΩ ×2 | 2 | kit ([Buy once](#buy-once)) | [R](https://www.amazon.com/dp/RES1) |
| JST-XH crimp pins | JST **SXH-001T-P0.6** | 4 (J5 plug) | bag ([Buy once](#buy-once)) | [DigiKey](https://www.digikey.com/x?k=SXH) |
| ESP32-C6 SuperMini | | 1 | 5-pack | [E](https://www.amazon.com/dp/ESP1) |
### Box
| Part | Per box | Sold as | Link |
|---|---|---|---|
| Tray | 1 each | | [box](../docs/controller-box.md) |
| Insert | 3 | from the tilters' pack of 100 | [I](https://www.amazon.com/dp/INS1) |
| M2 screw | 2 | any small pack | [search](https://www.amazon.com/s?k=M2) |
## One Tilt Hub
| Part | Per hub | Sold as | Link |
|---|---|---|---|
| ESP32-C6 SuperMini, **no pins soldered** | 1 | from the controllers' 5-pack | [E](https://www.amazon.com/dp/ESP1) |
| Wall plug | 1 | each | any |
## Buy once
| Part | Uses | Sold as | Link |
|---|---|---|---|
| M3 screw kit | 5 per tilter | kit | [K](https://www.amazon.com/dp/KIT1) |
| Resistor kit | 2 per controller | kit | [R](https://www.amazon.com/dp/RES1) |
| Heat-shrink kit | a few | kit | [H](https://www.amazon.com/dp/HEAT1) |
## Optional
### Solar: yes or no
| Part | Per controller | Sold as | Link |
|---|---|---|---|
| Solar panel | 1 to 6 | 3-pack | [P](https://www.amazon.com/dp/SUN1) |
| Tape | about 20 cm | 1 roll | any |
### No JST crimper
Leads, **ASXH22**: 2 per controller, in place of the crimp pins. [DigiKey](https://www.digikey.com/x?k=ASXH).
## Tools
Soldering iron.
"""
    GUIDE = """## Parts for one board

| Part | Qty | References | Step |
|---|---|---|---|
| 1M | 2 | R1, R2 | 1 |
| ESP32-C6 SuperMini (male pins on) | 1 | plugs into J1 / J2 | 13 |

## Which parts
"""

    def setUp(self):
        self.parts = inventory.parse(self.BOM, self.GUIDE)

    def rows(self, plan, **kw):
        return {r[0].key: r[1:] for r in inventory.order(self.parts, plan, **kw)}

    def test_rows_with_one_link_are_one_part(self):
        kit = self.parts['KIT1']
        self.assertEqual((kit.name, kit.pack, kit.per), ('M3 screw kit', 'kit', {'tilter': 5}))
        self.assertEqual(self.parts['INS1'].per, {'tilter': 6, 'controller': 3})
        self.assertEqual(self.parts['ESP1'].per, {'controller': 1, 'hub': 1})
        self.assertNotIn('housing', ' '.join(self.parts))          # printed parts are made, not bought
        self.assertEqual(self.parts['87180-066LF'].where['controller'], 'J9, J10, J11')
        self.assertEqual(self.parts['EEU-FR1A471'].where['controller'], 'C9')
        self.assertEqual(self.parts['RES1'].where['controller'], 'R1, R2')
        self.assertEqual(self.parts['ESP1'].where['controller'], 'J1, J2')
        self.assertEqual(self.parts['ASXH22'].optional, 'no-crimper')

    def test_two_sets_of_three(self):
        rows = self.rows(inventory.Plan([(3, False), (3, False)]))
        self.assertEqual(rows['MOTOR1'], (2, 3, 0, 6, 0))
        self.assertEqual(rows['INS1'], (1, 100, 0, 42, 58))
        self.assertEqual(rows['87180-066LF'][:4], (6, 1, 0, 6))    # one jack per used port, not 3 per controller
        self.assertEqual([rows[k][3] for k in ('CORD3', 'CORD6', 'CORD10')], [2, 2, 2])
        self.assertEqual(rows['ESP1'][3], 3)                       # 2 controllers + the hub
        self.assertEqual(rows['KIT1'], (1, 'kit', 0, 30, '–'))
        self.assertEqual(rows['HEAT1'][:4], (1, 'kit', 0, 1))
        self.assertNotIn('SUN1', rows)
        self.assertNotIn('ASXH22', rows)

    def test_cords_follow_the_rule(self):
        self.assertEqual(inventory.Plan([(1, False), (2, False), (3, True)]).cords(), {'3.3': 3, '6.6': 3, '10': 0})
        with self.assertRaises(ValueError):
            inventory.Plan([(4, False)])

    def test_have_and_on_order(self):
        plan = inventory.Plan([(3, False)], hub=0)
        rows = self.rows(plan, have={'MOTOR1': 2, 'RES1': 'kit', 'KIT1': 'plenty'}, on_order={'CORD3': 2})
        self.assertEqual(rows['MOTOR1'], (1, 3, 2, 3, 2))
        for covered in ('RES1', 'KIT1', 'CORD3'):
            self.assertNotIn(covered, rows)
        self.assertEqual(rows['ESP1'][3], 1)
        self.assertNotIn('wall-plug', rows)

    def test_options(self):
        rows = self.rows(inventory.Plan([(2, False)], solar=4, crimper=False))
        self.assertEqual(rows['SUN1'][:4], (2, 3, 0, 4))
        self.assertEqual(rows['ASXH22'][3], 2)
        self.assertNotIn('SXH-001T-P0.6', rows)
        self.assertIn('tape', ' '.join(rows))

    def test_output(self):
        plan = inventory.Plan([(3, True)])
        table = inventory.order_table(inventory.order(self.parts, plan))
        self.assertIn('| ☐ | [Motor](https://www.amazon.com/dp/MOTOR1) | Amazon | 1 | 3 | 0 | 3 | 0 |', table)
        self.assertIn('| ☐ | Wall plug | any |', table)
        self.assertEqual(inventory.order_table([]), '**Nothing left to order.**\n')
        stock = inventory.stock_tables(self.parts, plan)
        self.assertIn('6 (+3 per controller)', stock)
        self.assertIn('about 40 cm per tilter', stock)
        self.assertIn('1 per used port', stock)
        self.assertIn('3.3 ft + 6.6 ft + 6.6 ft', inventory.plan_text(plan))
        self.assertIn('| [Solar panel](https://www.amazon.com/dp/SUN1) | no |', inventory.optional_text(self.parts, plan))

    def test_real_bom_two_sets_of_three(self):
        parts = inventory.load()
        rows = {r[0].key: r for r in inventory.order(parts, inventory.Plan([(3, False), (3, False)]))}
        need = {k: r[4] for k, r in rows.items()}
        self.assertEqual((need['87180-066LF'], need['0ZRE0075FF1A'], need['B0GD19KJ4B']), (6, 6, 3))
        self.assertEqual([need[k] for k in ('B0C1VHVJTS', 'B0C1VJN3DL', 'B0C1VK4W51')], [2, 2, 2])
        self.assertEqual(need['B0F83XS7PW'], 6)
        for part, packs, pack, _, need_, spare in rows.values():
            self.assertTrue(part.url or part.store == 'any', part.name)
            if isinstance(pack, int):
                self.assertEqual(packs * pack - need_, spare, part.name)
        self.assertFalse([p for p in parts.values() if p.optional and p.key in need])

    def test_cli(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'inventory.md')
            args = ['new', '--set', '3', '--set', '2', '--have', 'B072BL2VX1=kit', '--on-order', 'B0F83XS7PW=3']
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(inventory.main(args + ['--out', out]), 0)
            with open(out) as f:
                text = f.read()
            for heading in ('## Contents', '## How to use', '## Plan', '## Orders', '### On order', '### To order',
                            '## Stock', '### Bench tools', '## Optional parts', '## Notes', '## Log'):
                self.assertIn(heading, text)
            self.assertNotIn('{{', text)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(inventory.main(args + ['--out', out]), 1)    # never overwrites
            for argv in (['parts'], ['order', '--set', '1'], ['new', '--set', '1']):
                with contextlib.redirect_stdout(io.StringIO()) as o:
                    self.assertEqual(inventory.main(argv), 0)
                self.assertTrue(o.getvalue())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(inventory.main(['order', '--set', '5']), 2)


if __name__ == '__main__':
    unittest.main()
