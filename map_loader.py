import struct
import os

MAP_W, MAP_H = 64, 64

class TileData:
    def __init__(self, x, y, h, data):
        self.x = x
        self.y = y
        self.h = h
        self.data = data

class MapObject:
    def __init__(self, tiles):
        self.tiles = tiles

class MapSegment:
    def __init__(self, mapnum, x, y, tiles, attributes, extra_floor_tiles, objects):
        self.mapnum = mapnum        # 地图编号
        self.x = x & ~0x3F          # 块起始x（64对齐）
        self.y = y & ~0x3F          # 块起始y（64对齐）
        self.tiles = tiles              # list of u32
        self.attributes = attributes    # list of u16
        self.extra_floor_tiles = extra_floor_tiles  # list of (x, y, data)
        self.objects = objects          # list of MapObject

def read_u32(f):
    return struct.unpack("<I", f.read(4))[0]

def read_u16(f):
    return struct.unpack("<H", f.read(2))[0]

def read_u8(f):
    return struct.unpack("<B", f.read(1))[0]

def get_map_filename(map_dir, mapnum, block_x, block_y):
    modx = (block_x >> 6) + 0x7e00
    mody = (block_y >> 6) + 0x7e00
    fname = f"{modx:04x}{mody:04x}.s32"
    return os.path.join(map_dir, str(mapnum), fname)

def load_map_segment(filename, mapnum=None, block_x=None, block_y=None):
    with open(filename, "rb") as f:
        tiles = [read_u32(f) for _ in range(MAP_W * 128)]
        quant = read_u16(f)
        extra_floor_tiles = []
        for _ in range(quant):
            a = read_u8(f)
            b = read_u8(f)
            c = read_u32(f)
            extra_floor_tiles.append((a, b, c))
        attributes = [read_u16(f) for _ in range(MAP_W * 128)]
        object_count = read_u32(f)
        objects = []
        for _ in range(object_count):
            _index = read_u16(f)
            num_tiles = read_u16(f)
            tile_list = []
            for _ in range(num_tiles):
                b = read_u8(f)
                c = read_u8(f)
                if b == 205 and c == 205:
                    f.read(5)
                    continue
                h = read_u8(f)
                data = read_u32(f)
                tile_list.append(TileData(b, c, h, data))
            objects.append(MapObject(tile_list))
        # 新增: 返回块起始坐标
        if mapnum is not None and block_x is not None and block_y is not None:
            return MapSegment(mapnum, block_x, block_y, tiles, attributes, extra_floor_tiles, objects)
        else:
            # 向下兼容原有调用
            return MapSegment(None, 0, 0, tiles, attributes, extra_floor_tiles, objects)

class MapSegmentManager:
    """
    动态加载和卸载地图块（segment）。管理所有活跃的segment。
    """
    def __init__(self, map_dir, mapnum, view_w=1200, view_h=900):
        self.map_dir = map_dir
        self.mapnum = mapnum
        self.view_w = view_w
        self.view_h = view_h
        self.segments = {}  # {(block_x, block_y): MapSegment}

    def needed_blocks(self, center_x, center_y):
        # 计算视窗需要哪些block（64对齐）
        tile_px = 24
        tile_py = 12
        # 估算窗口覆盖多少地图tile
        left = center_x - ((self.view_w // 2) // tile_px) * 2
        right = center_x + ((self.view_w // 2) // tile_px) * 2
        top = center_y - ((self.view_h // 2) // tile_py) * 2
        bottom = center_y + ((self.view_h // 2) // tile_py) * 2

        blocks = set()
        for bx in range((left & ~0x3F), (right & ~0x3F) + 1, 64):
            for by in range((top & ~0x3F), (bottom & ~0x3F) + 1, 64):
                blocks.add((bx, by))
        return blocks

    def update_segments(self, center_x, center_y):
        """
        保证视窗内所有需要的segment都已加载，不需要的自动卸载
        """
        needed = self.needed_blocks(center_x, center_y)
        # print("需要加载的块：", needed)
        # 加载新需要的
        for bx, by in needed:
            if (bx, by) not in self.segments:
                fname = get_map_filename(self.map_dir, self.mapnum, bx, by)
                # print("尝试加载：", fname, "存在？", os.path.exists(fname))
                if os.path.exists(fname):
                    seg = load_map_segment(fname, self.mapnum, bx, by)
                    self.segments[(bx, by)] = seg
        # 卸载不再需要的
        for key in list(self.segments.keys()):
            if key not in needed:
                del self.segments[key]

    def get_active_segments(self):
        """
        返回当前所有已加载的segment对象列表
        """
        return list(self.segments.values())