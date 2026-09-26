#!/usr/bin/env python3
"""Mirror a local music folder into an iPod — headless, with embedded artwork.

Modern macOS Finder "manages" iPods by validating and rewriting their database
on every connection, which wipes artwork and pops "cannot read iPod" dialogs.
This script takes a different route: rebuild the iPod's library database from
scratch (iTunesDB + SQLite + ArtworkDB + ithmb covers) using iOpenPod.

- Files already on the iPod are matched by MD5 and reused (incremental sync)
- Missing files are copied in; files no longer in the source are removed
- Metadata comes from embedded tags; falls back to "Artist/Album/NN. Title" paths
- Cover art is extracted from the embedded images in each audio file

Usage:
    python3 sync_ipod.py --music-dir ~/Music/iPod --ipod /Volumes/iPod
"""
import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from iopenpod.sync._db_io import read_existing_database
    from iopenpod.sync._track_conversion import track_dict_to_info
    from iopenpod.sync.database_commit import (
        DatabaseCommitPayload,
        write_database_commit,
    )
    from iopenpod.device.scanner import scan_for_ipods
    from iopenpod.device import set_current_device
except ImportError:
    sys.exit("缺少依赖：pip install iopenpod   （还需要系统装有 ffmpeg/ffprobe）")

AUDIO_EXT = {".m4a", ".mp3"}


def log(msg):
    print(f"[ipod-sync] {msg}", flush=True)


def md5(p: Path, cache: dict) -> str:
    st = p.stat()
    ent = cache.get(str(p))
    if ent and ent[0] == st.st_size and ent[1] == int(st.st_mtime):
        return ent[2]
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    cache[str(p)] = [st.st_size, int(st.st_mtime), h.hexdigest()]
    return h.hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(p)],
        capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def num(value, default=0):
    try:
        return int(str(value).split("/")[0].strip())
    except Exception:
        return default


def split_total(value):
    s = str(value or "")
    return int(s.split("/")[1]) if "/" in s else 0


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description="Sync a music folder into an iPod")
    ap.add_argument("--music-dir", required=True, type=Path,
                    help="folder containing your music (Artist/Album/NN. Title.m4a)")
    ap.add_argument("--ipod", default="/Volumes/iPod", type=Path,
                    help="mount point of the iPod (default: /Volumes/iPod)")
    ap.add_argument("--cache", default=Path.home() / ".cache" / "ipod_sync_md5.json",
                    type=Path, help="MD5 cache file for fast re-syncs")
    ap.add_argument("--no-delete-orphans", action="store_true",
                    help="keep files on the iPod that are no longer in the source")
    args = ap.parse_args()

    ipod: Path = args.ipod
    music_dir: Path = args.music_dir.expanduser()
    music_root = ipod / "iPod_Control" / "Music"
    if not music_root.is_dir():
        sys.exit(f"找不到 iPod 音乐目录：{music_root}（iPod 插好了吗？访达里能看到磁盘吗？）")

    # ── 1. collect source files ──────────────────────────────────
    local_files = sorted(p for p in music_dir.rglob("*") if p.suffix.lower() in AUDIO_EXT)
    if not local_files:
        sys.exit(f"音乐文件夹里没找到音频文件：{music_dir}")
    log(f"源文件 {len(local_files)} 个，计算 MD5…")
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(args.cache)
    local = {p: md5(p, cache) for p in local_files}
    args.cache.write_text(json.dumps(cache))
    log("源文件 MD5 完成")

    # ── 2. register device (needed for capability/hash detection) ─
    devices = scan_for_ipods()
    dev = None
    for d in devices:
        mp = str(getattr(d, "mount_path", "") or "").rstrip("/")
        log(f"设备: family={getattr(d, 'model_family', '?')} mount={mp}")
        if mp == str(ipod).rstrip("/"):
            dev = d
    if dev is None and len(devices) == 1:
        dev = devices[0]
    if dev is None:
        sys.exit("未找到 iPod 设备")
    set_current_device(dev)
    caps = dev.capabilities
    log(f"capabilities: checksum={dev.checksum_type} "
        f"sqlite={getattr(caps, 'uses_sqlite_db', '?')}")

    # ── 3. hash what's on the iPod and match ─────────────────────
    ipod_files = list(music_root.rglob("*"))
    ipod_files = [p for p in ipod_files if p.suffix.lower() in AUDIO_EXT]
    ipod_hash = {p: md5(p, cache) for p in ipod_files}
    args.cache.write_text(json.dumps(cache))
    log(f"iPod 现有文件 {len(ipod_files)} 个，MD5 完成")
    by_hash = {}
    for p, h in ipod_hash.items():
        by_hash.setdefault(h, p)

    local_hashes = set(local.values())
    reuse, to_copy = {}, []
    for p, h in local.items():
        if h in by_hash:
            reuse[p] = by_hash[h]
        else:
            to_copy.append(p)
    orphans = [p for p, h in ipod_hash.items() if h not in local_hashes]
    log(f"复用 {len(reuse)} 个；待拷贝 {len(to_copy)} 个；孤儿 {len(orphans)} 个")
    for p in to_copy:
        log(f"  待拷贝: {p.name}")
    for p in orphans:
        log(f"  孤儿: {p.name}")

    # ── 4. copy missing files ────────────────────────────────────
    copied = {}
    if to_copy:
        dirs = [p.parent.name for p in ipod_files]
        nums = [int(d[1:]) for d in dirs if d.startswith("F") and d[1:].isdigit()]
        next_idx = max(nums) + 1 if nums else 0
        rng = random.Random(int(time.time()))
        cur_dir, per_dir = None, 0
        for p in to_copy:
            if cur_dir is None or per_dir >= 25:
                cur_dir = music_root / f"F{next_idx:02d}"
                cur_dir.mkdir(exist_ok=True)
                next_idx += 1
                per_dir = 0
            dest = cur_dir / ("".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
                              + p.suffix.lower())
            log(f"拷贝 {p.name} -> {dest.relative_to(ipod)}")
            shutil.copy2(p, dest)
            copied[p] = dest
            per_dir += 1

    # ── 5. build track records from metadata ─────────────────────
    log("读取元数据…")
    now = int(time.time())
    rng2 = random.Random(42)

    def new_pid():
        return rng2.randrange(1, 2 ** 63)

    tracks = []
    untagged = []
    for p in local_files:
        j = probe(p)
        fmt = j.get("format", {})
        st = (j.get("streams") or [{}])[0]
        tags = dict(fmt.get("tags") or {})
        tags.update(st.get("tags") or {})
        if not tags.get("title"):
            untagged.append(p.name)
        dur = float(fmt.get("duration") or 0)
        loc_p = reuse.get(p) or copied.get(p)
        rel = ":" + str(loc_p.relative_to(ipod)).replace("/", ":")

        # untagged files: infer from "Artist/Album/NN. Title.ext" layout
        title = tags.get("title") or p.stem
        track_no = num(tags.get("track"))
        m = re.match(r"^(\d{1,3})[.、\s]+(.+)$", title)
        if not tags.get("title") and m:
            track_no = track_no or int(m.group(1))
            title = m.group(2).strip()
        album = tags.get("album") or p.parent.name
        artist = tags.get("artist") or p.parent.parent.name
        year = 0
        if tags.get("date"):
            year = num(str(tags.get("date"))[:4])
        elif tags.get("copyright"):
            ym = re.search(r"(19|20)\d{2}", str(tags.get("copyright")))
            if ym:
                year = int(ym.group(0))

        ext = p.suffix.lower()
        tracks.append(({
            "Title": title,
            "Artist": artist,
            "Album": album,
            "Album Artist": tags.get("album_artist") or artist,
            "Genre": tags.get("genre") or "",
            "Composer": tags.get("composer") or "",
            "Location": rel,
            "filetype": "MP3" if ext == ".mp3" else "M4A",
            "size": int(fmt.get("size") or p.stat().st_size),
            "length": int(round(dur * 1000)),
            "bitrate": int(round(int(fmt.get("bit_rate") or 0) / 1000)),
            "sample_rate_1": 44100,
            "sample_count": int(round(dur * 44100)),
            "year": year,
            "track_number": track_no,
            "total_tracks": split_total(tags.get("track")),
            "disc_number": num(tags.get("disc"), 1) or 1,
            "total_discs": split_total(tags.get("disc")),
            "db_track_id": new_pid(),
            "media_type": 1,
            "date_added": now,
            "date_released": 0,
            "gapless_track_flag": 1,
            "encoder": 1,
        }, p))
    if untagged:
        log(f"提示：{len(untagged)} 个文件无内嵌标签，已按文件名/文件夹推断: {untagged[:5]}...")
    tracks.sort(key=lambda x: (
        (x[0]["Album Artist"] or x[0]["Artist"]).lower(),
        x[0]["Album"].lower(), x[0]["disc_number"], x[0]["track_number"],
        x[0]["Title"].lower()))
    log(f"曲目构造完成 {len(tracks)} 首")

    infos = [track_dict_to_info(td) for td, _ in tracks]
    pc_map = {info.db_track_id: str(p) for info, (_, p) in zip(infos, tracks)}

    # ── 6. preserve existing on-device playlists (if any) ────────
    db = read_existing_database(ipod, include_playcounts=False)
    key2new = {(td["Title"], td["Album"], td["track_number"]): info.db_track_id
               for (td, _), info in zip(tracks, infos)}
    tid_map = {}
    for t in db["tracks"]:
        tid = t.get("tid") or t.get("track_id")
        k = (t.get("Title"), t.get("Album"), t.get("track_number"))
        if tid and k in key2new:
            tid_map[tid] = key2new[k]
    valid_ids = {i.db_track_id for i in infos}
    path_map = {td["Location"]: i.db_track_id for (td, _), i in zip(tracks, infos)}

    from iopenpod.sync._playlist_builder import (
        _playlist_track_ids_and_metadata, decode_raw_blob,
        _playlist_property_plist_raw, _playlist_description,
        _mhsd5_type_value, _phase_game_flag_value,
    )
    from iopenpod.itunesdb_writer.mhyp_writer import PlaylistInfo

    def convert_playlist_rows(rows):
        master_name, master_id, infos_pl = "iPod", None, []
        for pl in rows:
            if pl.get("master_flag"):
                master_name = pl.get("Title", master_name)
                master_id = pl.get("playlist_id")
                continue
            track_ids, item_meta = _playlist_track_ids_and_metadata(
                pl.get("items", []), tid_map, valid_ids, path_map)
            infos_pl.append(PlaylistInfo(
                name=pl.get("Title", "Untitled"),
                track_ids=track_ids,
                playlist_id=pl.get("playlist_id"),
                master=False,
                sortorder=pl.get("sort_order", 0),
                podcast_flag=pl.get("podcast_flag", 0),
                playlist_kind_flags=pl.get("playlist_kind_flags"),
                parent_folder_playlist_id=int(
                    pl.get("parent_folder_playlist_id")
                    or pl.get("unk0x30_playlist_ref") or 0),
                mhsd5_type=_mhsd5_type_value(pl),
                phase_game_flag=_phase_game_flag_value(pl),
                raw_mhod100=decode_raw_blob(pl.get("playlist_prefs")),
                raw_mhod102=decode_raw_blob(pl.get("playlist_settings")),
                raw_mhod55=_playlist_property_plist_raw(pl),
                playlist_description=_playlist_description(pl),
                item_metadata=item_meta,
            ))
        return master_name, master_id, infos_pl

    m_name, m_id, pl2 = convert_playlist_rows(db["dataset2_standard_playlists"])
    _, _, pl3 = convert_playlist_rows(db["dataset3_podcast_playlists"])
    log(f"主播放列表 '{m_name}'；保留普通播放列表 {len(pl2)} 个")

    # ── 7. write everything ──────────────────────────────────────
    payload = DatabaseCommitPayload(
        all_tracks=infos,
        pc_file_paths=pc_map,
        playlists=pl2,
        podcast_playlists=pl3,
        smart_playlists=[],
        master_playlist_name=m_name,
        master_playlist_id=m_id,
    )
    log("开始写入数据库…")
    ok = write_database_commit(str(ipod), payload,
                               progress_callback=log, raise_on_error=True)
    log(f"写入结果: {ok}")

    # ── 8. drop orphans after a successful write ─────────────────
    if ok and not args.no_delete_orphans:
        for p in orphans:
            log(f"删除孤儿 {p.relative_to(ipod)}")
            p.unlink()
    log(f"最终 iPod 文件数 {len(list(music_root.rglob('*')))}")

    art_db = ipod / "iPod_Control" / "Artwork" / "ArtworkDB"
    ithmbs = list(art_db.parent.glob("*.ithmb"))
    log(f"ArtworkDB: {art_db.stat().st_size}B; "
        f"ithmb: {sorted(p.name for p in ithmbs)}")
    print("DONE" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
