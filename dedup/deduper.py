from typing import List, Dict
from collections import defaultdict
from dedup.hasher import compute_xxhash, compute_md5, compute_sha1

class Deduper:
    def __init__(self, workspace):
        self.workspace = workspace

    def find_potential_duplicates(self):
        files = self.workspace.get_files()
        hash_map = defaultdict(list)
        for file in files:
            if not file['xxhash']:
                file['xxhash'] = compute_xxhash(file['path'])
                self.workspace.add_file(file['path'], file['size'], file['modified'], file['xxhash'], file['md5'], file['sha1'], file['status'])
            hash_map[file['xxhash']].append(file)
        return [group for group in hash_map.values() if len(group) > 1]

    def confirm_duplicates(self, potential_groups: List[List[Dict]]):
        confirmed = []
        for group in potential_groups:
            md5_map = defaultdict(list)
            for file in group:
                if not file['md5']:
                    file['md5'] = compute_md5(file['path'])
                    self.workspace.add_file(file['path'], file['size'], file['modified'], file['xxhash'], file['md5'], file['sha1'], file['status'])
                md5_map[file['md5']].append(file)
            for md5_group in md5_map.values():
                if len(md5_group) > 1:
                    confirmed.append(md5_group)
        return confirmed
