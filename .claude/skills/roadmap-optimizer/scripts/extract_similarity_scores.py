#!/usr/bin/env python3
"""
Extract Similarity Scores from Excel Files
===========================================
Reads the MAE, MAOC, and UNO similarity score Excel files and outputs
a summary JSON that can be used by the roadmap optimizer.

Run this once to extract the similarity data:
    python scripts/extract_similarity_scores.py

Output: data/similarity_scores.json
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any


def extract_similarity_data(file_path: str) -> Dict[str, Any]:
    """Extract similarity score data from an Excel file."""
    result = {
        "source_file": str(file_path),
        "sheets": [],
        "summary": {}
    }

    try:
        xl = pd.ExcelFile(file_path)
        result["sheet_names"] = xl.sheet_names

        for sheet_name in xl.sheet_names:
            sheet_info = {"name": sheet_name}
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheet_info["shape"] = list(df.shape)
                sheet_info["columns"] = list(df.columns)

                # Look for similarity score columns
                score_cols = [c for c in df.columns if 'score' in str(c).lower() or 'similarity' in str(c).lower()]
                if score_cols:
                    sheet_info["score_columns"] = score_cols
                    for col in score_cols:
                        if df[col].dtype in ['float64', 'int64']:
                            sheet_info[f"{col}_stats"] = {
                                "mean": float(df[col].mean()) if pd.notna(df[col].mean()) else None,
                                "min": float(df[col].min()) if pd.notna(df[col].min()) else None,
                                "max": float(df[col].max()) if pd.notna(df[col].max()) else None,
                                "count": int(df[col].count())
                            }

                # Sample first few rows (excluding temp table columns)
                sample_df = df.head(5)
                sheet_info["sample_data"] = sample_df.to_dict(orient='records')

            except Exception as e:
                sheet_info["error"] = str(e)

            result["sheets"].append(sheet_info)

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    base_path = Path(__file__).parent.parent
    data_dir = base_path / "data"
    data_dir.mkdir(exist_ok=True)

    # Files to process
    files = [
        "MAE_Similarity_Score.xlsx",
        "MAOC_Similarity_Score.xlsm",
        "UNO_Similarity_Score.xlsm"
    ]

    # Look for files in parent directory (workspace) or current directory
    search_paths = [
        base_path.parent,  # RoadmapSkill folder
        base_path,          # roadmap-optimizer folder
        Path.cwd(),         # Current directory
    ]

    results = {}

    for filename in files:
        model_name = filename.split("_")[0]  # MAE, MAOC, or UNO

        # Find the file
        file_path = None
        for search_path in search_paths:
            candidate = search_path / filename
            if candidate.exists():
                file_path = candidate
                break

        if file_path:
            print(f"Processing {filename}...")
            results[model_name] = extract_similarity_data(str(file_path))
        else:
            print(f"Warning: {filename} not found in search paths")
            results[model_name] = {"error": f"File not found: {filename}"}

    # Save combined results
    output_file = data_dir / "similarity_scores.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nSimilarity scores extracted to: {output_file}")

    # Print summary
    print("\n" + "="*60)
    print("SIMILARITY SCORES SUMMARY")
    print("="*60)

    for model, data in results.items():
        print(f"\n{model}:")
        if "error" in data and not data.get("sheets"):
            print(f"  Error: {data['error']}")
        else:
            print(f"  Sheets: {len(data.get('sheets', []))}")
            for sheet in data.get('sheets', [])[:3]:
                print(f"    - {sheet['name']}: {sheet.get('shape', 'N/A')}")
                if 'score_columns' in sheet:
                    print(f"      Score columns: {sheet['score_columns']}")


if __name__ == "__main__":
    main()
