"""结构化 JSON 日志（logging 生态，与 FastAPI/uvicorn 共用）"""
import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {"ts": time.time(), "level": record.levelname,
             "logger": record.name, "msg": record.getMessage()},
            ensure_ascii=False,
        )


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"brainflow.{name}")
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
