#!/usr/bin/env python3
"""월별 밀도·폴바셋 CSV를 대시보드용 통합 CSV 3개로 병합합니다."""

from __future__ import annotations

import csv
import filecmp
import re
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "mealdo"
MONTH_PATTERN = re.compile(r"^(\d{4})_(0[1-9]|1[0-2])$")

DATASETS = {
    "mealdo_sales": {
        "label": "밀도 매출",
        "required": {"기준일", "매장명", "품목명", "실매출"},
        "output": "밀도_일별매출_통합.csv",
    },
    "mealdo_waste": {
        "label": "밀도 폐기",
        "required": {"기준일", "매장명", "품목코드", "폐기수량", "폐기금액"},
        "output": "밀도_폐기데이터_통합.csv",
    },
    "paul_sales": {
        "label": "폴바셋 매출",
        "required": {"기준일", "매장명", "매출액_원"},
        "output": "폴바셋_일별매출_통합.csv",
    },
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with path.open("r", encoding=encoding, newline="") as source:
                reader = csv.DictReader(source)
                if not reader.fieldnames:
                    raise ValueError(f"헤더가 없는 CSV입니다: {path}")
                headers = [header.strip() for header in reader.fieldnames]
                if len(headers) != len(set(headers)):
                    raise ValueError(f"중복 컬럼이 있습니다: {path}")
                rows = []
                for row in reader:
                    normalized = {
                        (key.strip() if key else key): (value if value is not None else "")
                        for key, value in row.items()
                    }
                    rows.append(normalized)
                return headers, rows
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"CSV 인코딩을 확인할 수 없습니다: {path}") from last_error


def identify_dataset(headers: list[str], path: Path) -> str:
    header_set = set(headers)
    matches = [key for key, spec in DATASETS.items() if spec["required"].issubset(header_set)]
    if len(matches) != 1:
        raise ValueError(f"파일 유형을 하나로 판별할 수 없습니다: {path} (컬럼: {', '.join(headers)})")
    return matches[0]


def parse_date(value: str, path: Path, row_number: int) -> datetime:
    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    raise ValueError(f"기준일 형식을 확인해 주세요: {path} {row_number}행 ({text})")


def main() -> int:
    month_dirs = sorted(
        path for path in DATA_DIR.iterdir()
        if path.is_dir() and MONTH_PATTERN.fullmatch(path.name)
    )
    if not month_dirs:
        raise ValueError(f"YYYY_MM 형식의 월별 폴더가 없습니다: {DATA_DIR}")

    collected: dict[str, list[dict[str, str]]] = {key: [] for key in DATASETS}
    expected_headers: dict[str, list[str]] = {}

    for month_dir in month_dirs:
        monthly_files: dict[str, tuple[Path, list[str], list[dict[str, str]]]] = {}
        for csv_path in sorted(month_dir.glob("*.csv")):
            headers, rows = read_csv(csv_path)
            dataset = identify_dataset(headers, csv_path)
            if dataset in monthly_files:
                label = DATASETS[dataset]["label"]
                raise ValueError(f"{month_dir.name} 폴더에 {label} CSV가 2개 이상입니다.")
            monthly_files[dataset] = (csv_path, headers, rows)

        missing = [DATASETS[key]["label"] for key in DATASETS if key not in monthly_files]
        if missing:
            raise ValueError(f"{month_dir.name} 폴더에 파일이 없습니다: {', '.join(missing)}")

        expected_month = month_dir.name.replace("_", "-")
        for dataset, (csv_path, headers, rows) in monthly_files.items():
            if dataset not in expected_headers:
                expected_headers[dataset] = headers
            elif headers != expected_headers[dataset]:
                raise ValueError(
                    f"{DATASETS[dataset]['label']} 컬럼 구성이 월별로 다릅니다: {csv_path}"
                )

            for row_number, row in enumerate(rows, start=2):
                row_date = parse_date(row.get("기준일", ""), csv_path, row_number)
                if row_date.strftime("%Y-%m") != expected_month:
                    raise ValueError(
                        f"폴더 월과 기준일이 다릅니다: {csv_path} {row_number}행 "
                        f"({row_date:%Y-%m-%d})"
                    )
            collected[dataset].extend(rows)

    for dataset, spec in DATASETS.items():
        output_path = DATA_DIR / str(spec["output"])
        temp_path = output_path.with_suffix(".tmp")
        headers = expected_headers[dataset]
        rows = collected[dataset]
        rows.sort(key=lambda row: str(row.get("기준일", "")))
        try:
            with temp_path.open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=headers, extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)
            if output_path.exists() and filecmp.cmp(temp_path, output_path, shallow=False):
                print(f"[유지] {spec['label']}: 기존 통합 파일과 동일 ({len(rows):,}행)")
                continue

            for attempt in range(20):
                try:
                    temp_path.replace(output_path)
                    break
                except PermissionError as exc:
                    if attempt == 19:
                        raise PermissionError(
                            f"통합 파일이 다른 프로그램에서 사용 중입니다: {output_path.name}. "
                            "열려 있는 Excel을 닫고 다시 실행해 주세요."
                        ) from exc
                    time.sleep(0.25)
            print(f"[완료] {spec['label']}: {len(rows):,}행 -> {output_path.name}")
        finally:
            temp_path.unlink(missing_ok=True)

    print(f"월별 폴더 {len(month_dirs):,}개를 대시보드용 CSV 3개로 병합했습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, csv.Error) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
