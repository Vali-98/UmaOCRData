import sys, shutil, json, os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR"))
EVENTS_DIR = Path("events")

DATA_FORMAT_VERSION = 1


def get_latest_parquets(latest_data_path: Path):
    """
    Returns dict:
    {
      "deck": Path(...),
      "podium": Path(...),
      "statsheet": Path(...)
    }
    """
    files = list(latest_data_path.glob("*.parquet"))
    latest = {}

    for f in files:
        parts = f.stem.split("_")
        if len(parts) < 4:
            continue

        cls = parts[2]

        try:
            version = int(parts[3])
        except ValueError:
            continue

        if cls not in latest or version > latest[cls][1]:
            latest[cls] = (f, version)

    return {cls: data[0] for cls, data in latest.items()}


def get_parquet_versions(src_base: Path, classes):
    """
    Reads PARQUET_VERSIONS from config.json.
    Defaults to 1 for all classes if missing.
    """
    config_path = src_base / "config.json"

    # default: version 1 for all
    versions = {cls: 1 for cls in classes}

    if not config_path.exists():
        return versions

    try:
        with open(config_path, "r") as f:
            data = json.load(f)

        config_versions = data.get("PARQUET_VERSIONS", {})

        for cls in classes:
            if cls in config_versions:
                versions[cls] = config_versions[cls]

    except Exception:
        pass  # fallback silently

    return versions


def write_meta(dest_dir: Path, cm_id: str, parquet_versions: dict):
    meta = {
        "event": cm_id,
        "parquet_versions": parquet_versions,
        "data_format_version": DATA_FORMAT_VERSION
    }

    with open(dest_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def clear_directory(path: Path):
    if not path.exists():
        return
    for f in path.glob("*"):
        f.unlink()


def move_cm(cm_id: str):
    src_base = OUTPUT_DIR / cm_id / "finals"
    latest_data = src_base / "latest_data"

    if not latest_data.exists():
        raise FileNotFoundError(f"Missing latest_data for {cm_id}")

    dest_base = EVENTS_DIR / cm_id
    data_dir = dest_base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Clear old files
    clear_directory(data_dir)

    # Get latest parquet files
    parquet_map = get_latest_parquets(latest_data)
    if not parquet_map:
        raise ValueError(f"No parquet files found for {cm_id}")

    # Copy + rename parquet files
    for cls, src_path in parquet_map.items():
        dest_file = data_dir / f"{cls}.parquet"
        shutil.copy2(src_path, dest_file)

    # Copy CSV
    csv_src = src_base / "sheet_cache_merged.csv"
    csv_exists = False
    if csv_src.exists():
        shutil.copy2(csv_src, data_dir / "sheet_cache_merged.csv")
        csv_exists = True

    # Get parquet versions
    parquet_versions = get_parquet_versions(src_base, parquet_map.keys())

    # Write metadata (in cmX folder, not data/)
    write_meta(dest_base, cm_id, parquet_versions)

    # Logging
    print(f"✅ Moved {cm_id}")
    print(f"   → {data_dir}")
    print(f"   Parquets: {[f'{cls}.parquet' for cls in parquet_map.keys()]}")
    print(f"   CSV: {'yes' if csv_exists else 'no'}")
    print(f"   Versions: {parquet_versions}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python move.py cm6 [cm7 cm8 ...]")
        sys.exit(1)

    for cm_id in sys.argv[1:]:
        try:
            move_cm(cm_id)
        except Exception as e:
            print(f"❌ Failed {cm_id}: {e}")