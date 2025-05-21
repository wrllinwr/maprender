import struct

class PackFileEntry:
    def __init__(self, name, offset, size):
        self.name = name
        self.offset = offset
        self.size = size

class Pack:
    def __init__(self, pak_path, idx_path):
        self.pak_path = pak_path
        self.idx_path = idx_path
        self.entries = {}

    def load(self):
        with open(self.idx_path, "rb") as f:
            count = struct.unpack("<I", f.read(4))[0]
            for _ in range(count):
                offset = struct.unpack("<I", f.read(4))[0]
                name = f.read(20).split(b'\x00', 1)[0].decode('utf-8').lower()
                size = struct.unpack("<I", f.read(4))[0]
                self.entries[name] = PackFileEntry(name, offset, size)

    def raw_file_contents(self, name: str):
        entry = self.entries.get(name.lower())
        if not entry:
            return None
        with open(self.pak_path, "rb") as f:
            f.seek(entry.offset)
            return f.read(entry.size)