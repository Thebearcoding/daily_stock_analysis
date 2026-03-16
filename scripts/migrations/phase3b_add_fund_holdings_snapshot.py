#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3B: 创建 fund_holdings_snapshot 表。

幂等执行。SQLite 兼容。
用法：python scripts/migrations/phase3b_add_fund_holdings_snapshot.py
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 确保项目根目录在 sys.path 中
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run_migration():
    """创建 fund_holdings_snapshot 表（幂等）。"""
    from src.storage import DatabaseManager

    db = DatabaseManager()
    engine = db._engine

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "fund_holdings_snapshot" in existing_tables:
        logger.info("fund_holdings_snapshot 表已存在，跳过创建")
        return

    logger.info("创建 fund_holdings_snapshot 表 ...")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE fund_holdings_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_history_id INTEGER,
                fund_code VARCHAR(16) NOT NULL,
                fund_name VARCHAR(128),
                analysis_code VARCHAR(16) NOT NULL,
                source_type VARCHAR(32) NOT NULL DEFAULT 'unavailable',
                completeness VARCHAR(16) NOT NULL DEFAULT 'unavailable',
                as_of_date VARCHAR(32),
                stock_code VARCHAR(16) NOT NULL,
                stock_name VARCHAR(64),
                weight FLOAT,
                rank INTEGER,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fund_holdings_fund_code "
            "ON fund_holdings_snapshot (fund_code, as_of_date)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fund_holdings_analysis_history "
            "ON fund_holdings_snapshot (analysis_history_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fund_holdings_fetched_at "
            "ON fund_holdings_snapshot (fetched_at)"
        ))

    logger.info("fund_holdings_snapshot 表创建成功")


if __name__ == "__main__":
    run_migration()
