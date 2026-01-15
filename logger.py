import logging
from pathlib import Path
import sys

def setup_logger():
    """初始化日志配置：输出到控制台和文件"""
    # 创建日志目录
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        # 如果是脚本运行
        base_dir = Path(__file__).parent
        
    log_dir = base_dir / 'logs'
    # === 修改结束 ===

    log_dir.mkdir(exist_ok=True)

    # 日志格式：时间 | 级别 | 模块 | 消息
    log_format = "%(asctime)s | %(levelname)s | %(module)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 全局日志设置
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 1. 控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(console_handler)

    # 2. 文件Handler（按天滚动，保留7天）
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_dir / "window_list.log",
        maxBytes=10 * 1024 * 1024,  # 10MB/文件
        backupCount=7,  # 保留7个备份
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

setup_logger()
logger = logging.getLogger(__name__)