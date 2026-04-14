# -*- coding: utf-8 -*-
"""
日志配置模块

统一管理项目的日志配置
"""

import logging
import os
from typing import Optional


def configure_logging(
    level: int = logging.INFO, log_dir: str = "log", log_file: str = "app.log"
) -> logging.Logger:
    """
    配置项目日志系统

    Args:
        level: 日志级别
        log_dir: 日志文件目录
        log_file: 日志文件名

    Returns:
        logging.Logger: 配置好的根logger
    """
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        import sys

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        log_path = os.path.join(log_dir, log_file)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)

        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的logger

    Args:
        name: logger名称，为None时返回根logger

    Returns:
        logging.Logger: logger实例
    """
    return logging.getLogger(name) if name else logging.getLogger()
