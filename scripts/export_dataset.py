#!/usr/bin/env python3
"""
Export ingested dataset as a single offline file for easy sharing/backup.
Creates a self-contained ZIP with all raw pages, chunks, and FAISS index.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from webqa.config import SETTINGS


def export_dataset(output_file: str = None) -> None:
    """Export all ingested data into a single ZIP file."""
    
    data_dir = SETTINGS.raw_pages_path.parent.parent
    
    # Check if data exists
    if not SETTINGS.raw_pages_path.exists():
        print("❌ No ingested data found. Run: python scripts/run_model.py --ingest")
        raise SystemExit(1)
    
    # Create output filename with timestamp
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"webqa_dataset_export_{timestamp}.zip"
    
    output_path = PROJECT_ROOT / output_file
    
    print(f"\n📦 Exporting dataset to: {output_path}")
    print(f"   Data directory: {data_dir}")
    
    # Create ZIP archive
    shutil.make_archive(
        str(output_path.with_suffix('')),  # Remove .zip extension since make_archive adds it
        'zip',
        data_dir
    )
    
    # Print stats
    raw_pages = json.loads(SETTINGS.raw_pages_path.read_text(encoding='utf-8'))
    chunks_count = sum(1 for _ in SETTINGS.chunks_path.open(encoding='utf-8'))
    
    zip_size_mb = output_path.stat().st_size / (1024 * 1024)
    
    print(f"\n✅ Export complete!")
    print(f"   Websites: {len(raw_pages)}")
    print(f"   Chunks: {chunks_count}")
    print(f"   ZIP size: {zip_size_mb:.2f} MB")
    print(f"   Location: {output_path}")
    print(f"\n💡 To restore on another machine:")
    print(f"   unzip {output_path.name} -d {PROJECT_ROOT}")


def import_dataset(zip_file: str) -> None:
    """Import a previously exported dataset."""
    
    zip_path = Path(zip_file)
    if not zip_path.exists():
        print(f"❌ ZIP file not found: {zip_path}")
        raise SystemExit(1)
    
    data_dir = SETTINGS.raw_pages_path.parent.parent
    
    print(f"\n📥 Importing dataset from: {zip_path}")
    print(f"   Target directory: {data_dir}")
    
    shutil.unpack_archive(str(zip_path), data_dir)
    
    # Verify
    if SETTINGS.raw_pages_path.exists():
        raw_pages = json.loads(SETTINGS.raw_pages_path.read_text(encoding='utf-8'))
        chunks_count = sum(1 for _ in SETTINGS.chunks_path.open(encoding='utf-8'))
        print(f"\n✅ Import complete!")
        print(f"   Websites: {len(raw_pages)}")
        print(f"   Chunks: {chunks_count}")
    else:
        print("❌ Import failed - data not found after extraction")
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "import" and len(sys.argv) > 2:
            import_dataset(sys.argv[2])
        elif sys.argv[1] == "export":
            output = sys.argv[2] if len(sys.argv) > 2 else None
            export_dataset(output)
        else:
            print("Usage:")
            print("  python scripts/export_dataset.py export [optional_filename.zip]")
            print("  python scripts/export_dataset.py import <path_to_zip>")
    else:
        export_dataset()
