#!/usr/bin/env python3
"""변경된 CSV 브랜드의 데이터 범위를 data_update_log.csv에 자동 기록합니다."""

from __future__ import annotations

import csv
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "data" / "data_update_log.csv"
DATE_COLUMNS = ("일자", "기준일", "date")
BRAND_FILES = {
    "데르뜨": lambda: [
        path for path in (ROOT / "data" / "dertte").glob("*.csv")
        if path.name != "매출처_인코딩.csv"
    ],
    "밀도": lambda: [ROOT / "data" / "mealdo" / "밀도_일별매출_통합.csv"],
    "폴바셋": lambda: [ROOT / "data" / "mealdo" / "폴바셋_일별매출_통합.csv"],
}


def changed_csv_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "data"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    paths = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"').replace("\\", "/")
        if path.lower().endswith(".csv") and path != "data/data_update_log.csv":
            paths.append(path)
    return paths


def brands_for_paths(paths: list[str]) -> set[str]:
    brands: set[str] = set()
    for path in paths:
        if path.startswith("data/dertte/"):
            brands.add("데르뜨")
        if path.startswith("data/mealdo/") and "밀도_" in path:
            brands.add("밀도")
        if path.startswith("data/mealdo/") and "폴바셋_" in path:
            brands.add("폴바셋")
    return brands


def read_date_range(paths: list[Path]) -> tuple[str, str]:
    dates: list[datetime] = []
    for path in paths:
        if not path.exists():
            continue
        for encoding in ("utf-8-sig", "cp949"):
            try:
                with path.open("r", encoding=encoding, newline="") as source:
                    reader = csv.DictReader(source)
                    date_column = next((name for name in DATE_COLUMNS if name in (reader.fieldnames or [])), None)
                    if date_column is None:
                        break
                    for row in reader:
                        value = str(row.get(date_column, "")).strip()
                        for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
                            try:
                                dates.append(datetime.strptime(value, date_format))
                                break
                            except ValueError:
                                continue
                break
            except UnicodeDecodeError:
                continue
    if not dates:
        return "", ""
    return min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")


def main() -> int:
    changed_paths = changed_csv_paths()
    brands = brands_for_paths(changed_paths)
    if not brands:
        print("기록할 CSV 데이터 변경사항이 없습니다.")
        return 0

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with LOG_PATH.open("a", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=["brand", "updated_at", "data_start", "data_end", "note"],
        )
        if write_header:
            writer.writeheader()
        for brand in sorted(brands):
            data_start, data_end = read_date_range(BRAND_FILES[brand]())
            changed_names = [Path(path).name for path in changed_paths if brand in brands_for_paths([path])]
            writer.writerow({
                "brand": brand,
                "updated_at": now,
                "data_start": data_start,
                "data_end": data_end,
                "note": f"{', '.join(changed_names)} 갱신",
            })
            print(f"{brand} 데이터 업데이트 이력을 기록했습니다: {data_start} ~ {data_end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
