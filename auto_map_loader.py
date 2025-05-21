import os
from pack import Pack
from tileset import decode_tileset_data
from map_loader import load_map_segment

def get_map_filename(map_dir, x, y):
    modx = (x >> 6) + 0x7e00
    mody = (y >> 6) + 0x7e00
    fname = f"{modx:04x}{mody:04x}.s32"
    return os.path.join(map_dir, fname)

def collect_tileset_ids(map_segment):
    ids = set()
    for tile_info in map_segment.tiles:
        tile_id = tile_info >> 8
        ids.add(tile_id)
    return ids

def load_needed_tilesets(pack, tileset_ids):
    tilesets = {}
    for tile_id in tileset_ids:
        name = f"{tile_id}.til"
        tile_file_data = pack.raw_file_contents(name)
        if tile_file_data:
            tiles = decode_tileset_data(tile_file_data)
            tilesets[tile_id] = tiles
    return tilesets  # {tile_id: [tiles]}