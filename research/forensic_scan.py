#!/usr/bin/env python3
"""
Forensic scan to find missing filter logic from older project directories.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

# Target directories
SCAN_DIRS = [
    r"C:\Users\sydne\OneDrive\myprojectx2",
    r"C:\Users\sydne\OneDrive\myprojectx - Copy"
]

# Keywords to search for
KEYWORDS = [
    "2300", "0030",
    "NIGHT", "OVERNIGHT", "EXTENDED",
    "FILTER", "WINDOW", "SESSION",
    "ASIA", "LIQUIDITY", "SWEEP", "REJECTION", "FADE",
    "BIAS", "ORB_SIZE", "VOLATILITY", "RANGE",
    "CONDITION", "GATE"
]

# File extensions to scan
EXTENSIONS = [".py", ".md", ".txt", ".csv", ".ipynb"]

def scan_file(file_path):
    """Scan file for keywords and return matches."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Check for keywords (case insensitive)
        matches = []
        for keyword in KEYWORDS:
            if re.search(rf'\b{keyword}\b', content, re.IGNORECASE):
                matches.append(keyword)

        return matches if matches else None
    except Exception as e:
        return None

def get_file_purpose(file_path):
    """Try to determine file purpose from name and content."""
    name = Path(file_path).name.lower()

    if 'backtest' in name:
        return 'Backtest'
    elif 'filter' in name:
        return 'Filter'
    elif 'edge' in name:
        return 'Edge Discovery'
    elif 'validate' in name or 'validation' in name:
        return 'Validation'
    elif 'analysis' in name or 'analyze' in name:
        return 'Analysis'
    elif 'feature' in name:
        return 'Feature Engineering'
    elif 'setup' in name:
        return 'Setup/Config'
    elif 'audit' in name:
        return 'Audit'
    elif 'test' in name:
        return 'Test'
    else:
        return 'Unknown'

def scan_directory(root_dir):
    """Recursively scan directory for relevant files."""
    results = []

    if not os.path.exists(root_dir):
        print(f"Directory not found: {root_dir}")
        return results

    for root, dirs, files in os.walk(root_dir):
        # Skip certain directories
        skip_dirs = {'.git', '__pycache__', '.venv', 'node_modules', '.pytest_cache'}
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            ext = Path(file).suffix.lower()
            if ext in EXTENSIONS:
                file_path = os.path.join(root, file)
                matches = scan_file(file_path)

                if matches:
                    purpose = get_file_purpose(file_path)
                    results.append({
                        'path': file_path,
                        'ext': ext,
                        'purpose': purpose,
                        'keywords': matches
                    })

    return results

def main():
    all_results = []

    print("=" * 120)
    print("FORENSIC SCAN - SEARCHING FOR MISSING FILTER LOGIC")
    print("=" * 120)
    print()

    for scan_dir in SCAN_DIRS:
        print(f"Scanning: {scan_dir}")
        results = scan_directory(scan_dir)

        if results:
            print(f"  Found {len(results)} relevant files")
            all_results.extend(results)
        else:
            print(f"  No relevant files found (or directory doesn't exist)")
        print()

    if not all_results:
        print("No files found matching search criteria.")
        return

    # Sort by relevance (number of keyword matches)
    all_results.sort(key=lambda x: len(x['keywords']), reverse=True)

    print("=" * 120)
    print(f"RESULTS - {len(all_results)} FILES FOUND")
    print("=" * 120)
    print()

    # Group by purpose
    by_purpose = defaultdict(list)
    for result in all_results:
        by_purpose[result['purpose']].append(result)

    for purpose in sorted(by_purpose.keys()):
        files = by_purpose[purpose]
        print(f"\n{purpose} ({len(files)} files)")
        print("-" * 120)

        for f in files[:10]:  # Show top 10 per category
            rel_path = f['path'].replace(r'C:\Users\sydne\OneDrive\\', '')
            keywords_str = ', '.join(sorted(set(f['keywords']))[:8])
            print(f"  {rel_path}")
            print(f"    Keywords: {keywords_str}")

    # Write detailed results to CSV
    output_file = Path(__file__).parent / "forensic_scan_results.csv"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("file_path,file_type,purpose,keyword_count,keywords\n")
        for result in all_results:
            keywords_str = ';'.join(sorted(set(result['keywords'])))
            f.write(f'"{result["path"]}","{result["ext"]}","{result["purpose"]}",{len(result["keywords"])},"{keywords_str}"\n')

    print()
    print("=" * 120)
    print(f"Full results written to: {output_file}")
    print("=" * 120)

if __name__ == "__main__":
    main()
