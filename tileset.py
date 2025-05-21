import struct
import io
import numpy as np

def decode_tileset_data(data: bytes):
    cursor = io.BytesIO(data)
    num_tiles = struct.unpack("<H", cursor.read(2))[0]
    _waste16 = struct.unpack("<H", cursor.read(2))[0]
    offsets = [struct.unpack("<I", cursor.read(4))[0] for _ in range(num_tiles)]
    _w32 = struct.unpack("<I", cursor.read(4))[0]
    base_offset = cursor.tell()
    tiles = []
    for t in offsets:
        cursor.seek(base_offset + t)
        v1 = struct.unpack("<B", cursor.read(1))[0]
        # 判断tile是否为压缩镜像格式
        if (v1 & 2) != 0:
            # Rust: 镜像tile解码
            x = struct.unpack("<B", cursor.read(1))[0]
            y = struct.unpack("<B", cursor.read(1))[0]
            _w = struct.unpack("<B", cursor.read(1))[0]
            h = struct.unpack("<B", cursor.read(1))[0]
            mirrored_tile_data = np.zeros((24, 48), dtype=np.uint16)
            for i in range(h):
                num8 = struct.unpack("<B", cursor.read(1))[0]
                num_segments = num8
                skip_index = 0
                for _ in range(num_segments):
                    num = struct.unpack("<B", cursor.read(1))[0]
                    skip = num // 2
                    seg_width = struct.unpack("<B", cursor.read(1))[0]
                    skip_index += skip
                    for pixel in range(seg_width):
                        val = struct.unpack("<H", cursor.read(2))[0]
                        xx = x + skip_index + pixel
                        yy = y + i
                        if 0 <= yy < 24 and 0 <= xx < 48:
                            mirrored_tile_data[yy, xx] = val
                    skip_index += seg_width
            tiles.append(mirrored_tile_data)
        else:
            # 标准tile，288个u16，重建成24x48镜像
            tile_data = [struct.unpack("<H", cursor.read(2))[0] for _ in range(288)]
            mirrored_tile_data = np.zeros((24, 48), dtype=np.uint16)
            ind_offset = 0
            for i in range(24):
                width = 2 * (i + 1)
                if i > 11:
                    width -= 4 * (i - 11)
                left_start = 24 - width
                right_start = 24
                for j in range(width):
                    d = tile_data[ind_offset]
                    ind_offset += 1
                    mirrored_tile_data[i, left_start + j] = d    # 左半
                    mirrored_tile_data[i, right_start + j] = d   # 右半
            tiles.append(mirrored_tile_data)
    return tiles  # [np.array 24x48,uint16]