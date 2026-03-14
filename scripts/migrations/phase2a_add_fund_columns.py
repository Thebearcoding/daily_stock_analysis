#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2A 一次性迁移脚本：为 analysis_history 表新增基金领域字段。

用法：
    python scripts/migrations/phase2a_add_fund_columns.py

幂等设计：
    - 使用 PRAGMA table_info() 检测列是否已存在
    - 已存在的列跳过，不报错
    - 索引使用 CREATE INDEX IF NOT EXISTS

注意：
    - 仅支持 SQLite（当前项目唯一数据库引擎）
    - Base.metadata.create_all() 不会 ALTER 已有表，因此需要此脚本
"""

import logging
import os
import sys

# 把项目根目录加到 sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

# 新增列定义：(列名, SQL 类型, 默认值表达式)
NEW_COLUMNS = [
    ("asset_type", "VARCHAR(16) NOT NULL DEFAULT 'stock'"),
    ("analysis_kind", "VARCHAR(32) NOT NULL DEFAULT 'stock_analysis'"),
    ("analysis_mode", "VARCHAR(16)"),
    ("input_code", "VARCHAR(16)"),
    ("input_name", "VARCHAR(128)"),
]

# 新增索引
NEW_INDEXES = [
    ("ix_analysis_asset_type", "asset_type, created_at"),
    ("ix_analysis_input_code", "input_code, created_at"),
]


def get_existing_columns(engine) -> set:
    """获取 analysis_history 表的现有列名集合。"""
    with engine.connect() as conn:
        result = conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(analysis_history)")
        )
        return {row[1] for row in result.fetchall()}


def run_migration():
    """执行迁移。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db = DatabaseManager.get_instance()
    engine = db._engine

    existing = get_existing_columns(engine)
    logger.info(f"现有列: {sorted(existing)}")

    added = 0
    with engine.connect() as conn:
        for col_name, col_def in NEW_COLUMNS:
            if col_name in existing:
                logger.info(f"  列 '{col_name}' 已存在，跳过")
                continue
            sql = f"ALTER TABLE analysis_history ADD COLUMN {col_name} {col_def}"
            logger.info(f"  执行: {sql}")
            conn.execute(__import__("sqlalchemy").text(sql))
            added += 1

        for idx_name, idx_columns in NEW_INDEXES:
            sql = (
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON analysis_history ({idx_columns})"
            )
            logger.info(f"  执行: {sql}")
            conn.execute(__import__("sqlalchemy").text(sql))

        conn.commit()

    logger.info(f"迁移完成：新增 {added} 列, {len(NEW_INDEXES)} 个索引")

    # 验证
    updated = get_existing_columns(engine)
    for col_name, _ in NEW_COLUMNS:
        if col_name not in updated:
            logger.error(f"验证失败：列 '{col_name}' 未找到！")
            sys.exit(1)
    logger.info("验证通过：所有新列均已存在")


if __name__ == "__main__":
    run_migration()
