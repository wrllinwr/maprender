import os
import sdl2
import sdl2.ext
import numpy as np
from pack import Pack
from tileset import decode_tileset_data
from map_loader import load_map_segment, MAP_W, MAP_H, MapSegmentManager

def collect_tileset_ids_from_segments(segments):
    """收集所有已加载块用到的tile_id集合"""
    ids = set()
    for seg in segments:
        for tile_info in seg.tiles:
            tile_id = tile_info >> 8
            ids.add(tile_id)
        for x, y, c in getattr(seg, "extra_floor_tiles", []):
            ids.add(c >> 8)
        for obj in getattr(seg, "objects", []):
            for tdata in getattr(obj, "tiles", []):
                ids.add(tdata.data >> 8)
    return ids

def load_needed_tilesets(pack, tileset_ids):
    tilesets = {}
    for tile_id in tileset_ids:
        name = f"{tile_id}.til"
        tile_file_data = pack.raw_file_contents(name)
        if tile_file_data:
            tiles = decode_tileset_data(tile_file_data)
            tilesets[tile_id] = tiles
    return tilesets  # {tile_id: [np.array 24x48, ...]}

def rgb555_to_surface(tile_data):
    arr = tile_data.astype(np.uint16)
    r = ((arr >> 10) & 0x1f) << 3
    g = ((arr >> 5) & 0x1f) << 3
    b = (arr & 0x1f) << 3
    rgb = np.stack([r, g, b, np.full_like(r, 255)], axis=-1).astype(np.uint8)
    rgb = np.ascontiguousarray(rgb)
    surface = sdl2.SDL_CreateRGBSurfaceFrom(
        rgb.ctypes.data, 48, 24, 32, 48 * 4,
        0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000)
    sdl2.SDL_SetColorKey(surface, sdl2.SDL_TRUE, sdl2.SDL_MapRGB(surface.contents.format, 0, 0, 0))
    return surface


def pil_to_texture(renderer, surface):
    texture = sdl2.SDL_CreateTextureFromSurface(renderer.sdlrenderer, surface)
    sdl2.SDL_FreeSurface(surface)
    return texture

def main():
    map_dir = "D:/Game/map"  # 注意：这里应该是地图根目录

    # 染柳村
    mapnum = 4
    x, y = 33068, 32806  # 当前地图（世界）坐标

    # 死亡那个地方
    # mapnum = 0
    # x, y = 32768, 32768  # 当前地图（世界）坐标

    offset_x, offset_y = 400, 200

    # 初始化地图分块动态管理
    # manager = MapSegmentManager(os.path.join(map_dir, str(mapnum)), mapnum)
    manager = MapSegmentManager(map_dir, mapnum)
    center_x, center_y = x, y

    pack = Pack("D:/Game/Tile.pak", "D:/Game/Tile.idx")
    pack.load()

    sdl2.ext.init()
    window = sdl2.ext.Window("Map Render", size=(1200, 900))
    window.show()
    renderer = sdl2.ext.Renderer(window)

    tile_textures = {}  # {tile_id: [texture ...]}
    loaded_tilesets = set()
    running = True
    MOVE_X = 24
    MOVE_Y = 12

    while running:
        for event in sdl2.ext.get_events():
            if event.type == sdl2.SDL_QUIT:
                running = False
                break
            elif event.type == sdl2.SDL_KEYDOWN:
                key = event.key.keysym.sym
                if key in (sdl2.SDLK_LEFT, sdl2.SDLK_a):
                    offset_x += MOVE_X
                    center_x -= 2  # 地图坐标左移
                elif key in (sdl2.SDLK_RIGHT, sdl2.SDLK_d):
                    offset_x -= MOVE_X
                    center_x += 2
                elif key in (sdl2.SDLK_UP, sdl2.SDLK_w):
                    offset_y += MOVE_Y
                    center_y -= 2
                elif key in (sdl2.SDLK_DOWN, sdl2.SDLK_s):
                    offset_y -= MOVE_Y
                    center_y += 2

        # 1. 动态加载/卸载分块
        manager.update_segments(center_x, center_y)
        segments = manager.get_active_segments()

        # 2. 动态收集所有用到的tile_id，并准备贴图
        needed_tileset_ids = collect_tileset_ids_from_segments(segments)
        new_needed = needed_tileset_ids - loaded_tilesets

        if new_needed:
            tilesets = load_needed_tilesets(pack, new_needed)
            for tile_id, tile_list in tilesets.items():
                textures = []
                for tile_data in tile_list:
                    textures.append(pil_to_texture(renderer, rgb555_to_surface(tile_data)))
                tile_textures[tile_id] = textures
            loaded_tilesets |= new_needed
        
        renderer.clear(sdl2.ext.Color(0, 0, 0))
        TILE_W, TILE_H = 48, 24

        # 3. 渲染所有已加载块
        # 1. 收集所有块中的物体和extra_floor_tiles，生成全局渲染列表
        all_render_tiles = []
        for seg in segments:
            # extra_floor_tiles（地面附加物体），层级固定为0
            for x, y, c in getattr(seg, "extra_floor_tiles", []):
                world_x = seg.x + (x // 2)
                world_y = seg.y + y
                tile_id = c >> 8
                subtile = c & 0xFF
                all_render_tiles.append({
                    "type": "extra",
                    "h": 0,
                    "world_x": world_x,
                    "world_y": world_y,
                    "tile_id": tile_id,
                    "subtile": subtile,
                    "half": x % 2,
                })
            # objects（建筑、树、道具等，有层级h）
            for obj in getattr(seg, "objects", []):
                for tdata in getattr(obj, "tiles", []):
                    world_x = seg.x + (tdata.x // 2)
                    world_y = seg.y + tdata.y
                    tile_id = tdata.data >> 8
                    subtile = tdata.data & 0xFF
                    all_render_tiles.append({
                        "type": "object",
                        "h": getattr(tdata, "h", 0),
                        "world_x": world_x,
                        "world_y": world_y,
                        "tile_id": tile_id,
                        "subtile": subtile,
                        "half": tdata.x % 2,
                    })

        # 2. 排序：先按层级h，再按world_y，再按world_x
        all_render_tiles.sort(key=lambda t: (t["h"], t["world_y"], t["world_x"]))

        # 3. 渲染地板（主tile），原有遍历结构即可（按块/行/列，不需要全局排序）
        for seg in segments:
            for a in range(MAP_W):
                for b in range(MAP_H):
                    idx_left = b * 128 + 2 * a
                    idx_right = b * 128 + 2 * a + 1
                    world_x = seg.x + a
                    world_y = seg.y + b

                    # 左半格
                    if idx_left < len(seg.tiles):
                        tile_info = seg.tiles[idx_left]
                        tile_id = tile_info >> 8
                        subtile = tile_info & 0xFF
                        texs = tile_textures.get(tile_id)
                        if texs and 0 <= subtile < len(texs):
                            tex = texs[subtile]
                            px = (world_x - center_x) * 24 + (world_y - center_y) * 24 + offset_x
                            py = (world_y - center_y) * 12 - (world_x - center_x) * 12 + offset_y
                            src_rect_left = sdl2.SDL_Rect(0, 0, 24, 24)
                            dst_rect_left = sdl2.SDL_Rect(px, py, 24, 24)
                            sdl2.SDL_RenderCopy(renderer.sdlrenderer, tex, src_rect_left, dst_rect_left)

                    # 右半格
                    if idx_right < len(seg.tiles):
                        tile_info = seg.tiles[idx_right]
                        tile_id = tile_info >> 8
                        subtile = tile_info & 0xFF
                        texs = tile_textures.get(tile_id)
                        if texs and 0 <= subtile < len(texs):
                            tex = texs[subtile]
                            px = (world_x - center_x) * 24 + (world_y - center_y) * 24 + offset_x
                            py = (world_y - center_y) * 12 - (world_x - center_x) * 12 + offset_y
                            src_rect_right = sdl2.SDL_Rect(24, 0, 24, 24)
                            dst_rect_right = sdl2.SDL_Rect(px + 24, py, 24, 24)
                            sdl2.SDL_RenderCopy(renderer.sdlrenderer, tex, src_rect_right, dst_rect_right)

        # 4. 按排序后的全局渲染列表画出所有建筑和地面物体
        for t in all_render_tiles:
            px = (t["world_x"] - center_x) * 24 + (t["world_y"] - center_y) * 24 + offset_x
            if t["half"]:
                px += 24
            py = (t["world_y"] - center_y) * 12 - (t["world_x"] - center_x) * 12 + offset_y
            texs = tile_textures.get(t["tile_id"])
            if texs and 0 <= t["subtile"] < len(texs):
                tex = texs[t["subtile"]]
                # 你可以根据对象类型调整大小（如建筑48x48，地面48x24等）
                dst_rect = sdl2.SDL_Rect(px, py, 48, 24)
                sdl2.SDL_RenderCopy(renderer.sdlrenderer, tex, None, dst_rect)

        renderer.present()
        sdl2.SDL_Delay(16)

    # 清理
    for texs in tile_textures.values():
        for tex in texs:
            if tex:
                sdl2.SDL_DestroyTexture(tex)
    sdl2.ext.quit()

if __name__ == "__main__":
    main()