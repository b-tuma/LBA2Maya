# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Copyright (C) 2016  Vegard Nossum <vegard.nossum@gmail.com>

import io
import struct


class HQRReader(object):
    """
    Read compressed and uncompressed files from an LBA .HQR archive.
    """

    def __init__(self, path):
        self.path = path

    def __getitem__(self, index):
        with open(self.path, 'rb') as f:
            def u8():
                return struct.unpack('<B', f.read(1))[0]

            def u16():
                return struct.unpack('<H', f.read(2))[0]

            def u32():
                return struct.unpack('<I', f.read(4))[0]

            f.seek(4 * index)
            offset = u32()
            f.seek(offset)

            size_full = u32()
            size_compressed = u32()
            compression_type = u16()

            if compression_type == 0:
                # No compression
                return io.BytesIO(f.read(size_compressed))

            decompressed = bytearray()
            while True:
                flags = u8()
                for i in range(8):
                    if (flags >> i) & 1:
                        decompressed.append(u8())
                        if len(decompressed) == size_full:
                            return io.BytesIO(decompressed)
                    else:
                        header = u16()
                        offset = 1 + (header >> 4)
                        length = 1 + compression_type + (header & 15)

                        for i in range(length):
                            decompressed.append(decompressed[-offset])

                        if len(decompressed) >= size_full:
                            return io.BytesIO(decompressed[:size_full])
