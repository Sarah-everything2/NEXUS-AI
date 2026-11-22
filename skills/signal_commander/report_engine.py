"""Signal Commander report generation."""

import json
from datetime import datetime
from pathlib import Path


def save_report(data):
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = report_dir / f"signal_report_{timestamp}.json"

    report_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )

    print(f"[REPORT SAVED] {report_file}")
    return str(report_file)
