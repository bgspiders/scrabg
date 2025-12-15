import json
from pathlib import Path
from typing import Any, Dict


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "taskInfo" not in data or "workflowSteps" not in data:
        raise ValueError("配置缺少 taskInfo 或 workflowSteps")
    return data

