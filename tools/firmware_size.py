#!/usr/bin/env python3
"""How much room a firmware image leaves in its smallest app slot, and a floor CI fails under.

  tools/firmware_size.py <image.bin> <partitions.csv> --floor <bytes>
Prints one line and exits 1 when the free bytes are under the floor. Needs no ESP-IDF.
"""
import argparse
import os
import sys


def _size(text):
    """A partitions.csv size: hex (0x1F0000), decimal, or with K / M."""
    t = text.strip().upper()
    if t.endswith('K'):
        return int(t[:-1], 0) * 1024
    if t.endswith('M'):
        return int(t[:-1], 0) * 1024 * 1024
    return int(t, 0)


def headroom(image_size, partitions_csv_text):
    """(smallest app slot, bytes free in it) for an image of image_size bytes."""
    slots = []
    for line in partitions_csv_text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        cols = [c.strip() for c in line.split(',')]
        if len(cols) >= 5 and cols[1] == 'app':
            slots.append(_size(cols[4]))
    if not slots:
        raise ValueError('no app slot in the partition table')
    slot = min(slots)
    return slot, slot - image_size


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('image')
    ap.add_argument('partitions')
    ap.add_argument('--floor', type=int, required=True, help='fewest free bytes allowed')
    a = ap.parse_args(argv)
    size = os.path.getsize(a.image)
    slot, free = headroom(size, open(a.partitions).read())
    print('%s: 0x%x of 0x%x used, %d bytes (%d KB) free, floor %d KB'
          % (os.path.basename(a.image), size, slot, free, free // 1024, a.floor // 1024))
    return 0 if free >= a.floor else 1


if __name__ == '__main__':
    sys.exit(main())


def share_used(used, total):
    """Throwaway for the coverage gate test pull request (#238): never merged."""
    if total <= 0:
        return 0.0
    return 100.0 * used / total
