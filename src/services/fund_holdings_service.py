# -*- coding: utf-8 -*-
"""
===================================
Fund Holdings Service (Phase 3B)
===================================

Responsibilities:
1. Fetch fund disclosed holdings via akshare (fund_portfolio_hold_em)
2. Persist snapshots to fund_holdings_snapshot table
3. Load cached snapshots by analysis_history_id
4. Build unavailable responses for unsupported cases

Design constraints:
- is_realtime is always False (quarterly disclosure != real-time positions)
- source_type enum: 'fund_disclosed_holdings' | 'unavailable'
- completeness enum: 'low' | 'unavailable'
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.storage import DatabaseManager, FundHoldingsSnapshot

logger = logging.getLogger(__name__)

# ── 常量 ──

SOURCE_DISCLOSED = "fund_disclosed_holdings"
SOURCE_UNAVAILABLE = "unavailable"

COMPLETENESS_LOW = "low"
COMPLETENESS_UNAVAILABLE = "unavailable"


class FundHoldingsService:
    """基金持仓快照服务。"""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    # ── 公开方法 ──

    def get_holdings_for_fund(
        self,
        fund_code: str,
        persist_snapshot: bool = False,
        analysis_code: Optional[str] = None,
        fund_name: Optional[str] = None,
        analysis_name: Optional[str] = None,
        mapping_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取基金持仓（季度披露口径）。

        流程：
        1. 通过现有映射链路解析 fund_code → analysis_code
        2. 尝试抓取季度披露持仓
        3. 成功时返回 source_type='fund_disclosed_holdings'
        4. 失败时返回 source_type='unavailable'

        Args:
            fund_code: 基金代码
            persist_snapshot: 是否将快照存入 fund_holdings_snapshot

        Returns:
            持仓响应字典
        """
        # Step 1: 解析映射
        if analysis_code is None:
            analysis_code, fund_name, analysis_name, mapping_note = self._resolve_fund(fund_code)

        # Step 2: 尝试抓取
        items, as_of_date = self._fetch_disclosed_holdings(analysis_code)

        if not items:
            return self._build_unavailable_response(
                fund_code=fund_code,
                fund_name=fund_name,
                analysis_code=analysis_code,
            )

        response = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "analysis_code": analysis_code,
            "analysis_name": analysis_name,
            "source_type": SOURCE_DISCLOSED,
            "completeness": COMPLETENESS_LOW,
            "as_of_date": as_of_date,
            "is_realtime": False,
            "items": items,
        }

        # Step 3: 可选持久化
        if persist_snapshot:
            try:
                self._save_snapshot_rows(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    analysis_code=analysis_code,
                    source_type=SOURCE_DISCLOSED,
                    completeness=COMPLETENESS_LOW,
                    as_of_date=as_of_date,
                    items=items,
                    analysis_history_id=None,
                )
            except Exception as e:
                logger.warning(f"持仓快照存储失败（不影响返回）: {e}")

        return response

    def get_holdings_for_history_record(
        self,
        record_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        获取历史记录关联的持仓快照。

        流程：
        1. 查 analysis_history 记录
        2. 验证 asset_type='fund'
        3. 优先读取已有快照
        4. 无快照时懒加载抓取并绑定

        Args:
            record_id: analysis_history 主键

        Returns:
            持仓响应字典，或 None（记录不存在/不是基金）
        """
        # Step 1: 查记录
        record = self.db.get_analysis_history_by_id(record_id)
        if not record:
            return None
        if getattr(record, 'asset_type', 'stock') != 'fund':
            return None

        fund_code = record.input_code or record.code
        fund_name = record.input_name
        analysis_code = record.code

        # Step 2: 尝试读已有快照
        cached = self._load_snapshot_by_record_id(record_id)
        if cached:
            return cached

        # Step 3: 懒加载抓取
        items, as_of_date = self._fetch_disclosed_holdings(analysis_code)

        if not items:
            return self._build_unavailable_response(
                fund_code=fund_code,
                fund_name=fund_name,
                analysis_code=analysis_code,
            )

        # Step 4: 存快照并绑定 analysis_history_id
        try:
            self._save_snapshot_rows(
                fund_code=fund_code,
                fund_name=fund_name,
                analysis_code=analysis_code,
                source_type=SOURCE_DISCLOSED,
                completeness=COMPLETENESS_LOW,
                as_of_date=as_of_date,
                items=items,
                analysis_history_id=record_id,
            )
        except Exception as e:
            logger.warning(f"绑定历史记录的持仓快照存储失败: {e}")

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "analysis_code": analysis_code,
            "analysis_name": record.name,
            "source_type": SOURCE_DISCLOSED,
            "completeness": COMPLETENESS_LOW,
            "as_of_date": as_of_date,
            "is_realtime": False,
            "items": items,
        }

    # ── 内部方法 ──

    @staticmethod
    def _resolve_fund(fund_code: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """
        复用现有映射链路解析基金代码。

        Returns:
            (analysis_code, fund_name, analysis_name, mapping_note)
        """
        try:
            from src.services.fund_mapping import resolve_code
            return resolve_code(fund_code)
        except Exception as e:
            logger.warning(f"基金映射失败，回退原始代码 {fund_code}: {e}")
            try:
                from src.services.fund_mapping import get_fund_name

                fund_name = get_fund_name(fund_code, allow_placeholder=False)
            except Exception:
                fund_name = None
            return fund_code, fund_name, fund_name, None

    @staticmethod
    def _fetch_disclosed_holdings(
        analysis_code: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        通过 akshare 抓取基金季度披露持仓。

        使用 ak.fund_portfolio_hold_em(symbol, date) 获取最新季度持仓。
        注意：这是季度披露口径，非实时 ETF 成分股。
        fail-open：任何异常返回空列表。

        Returns:
            (items_list, as_of_date_string)
        """
        try:
            import akshare as ak
            current_year = str(datetime.now().year)
            from src.services.fund_mapping import execute_fund_data_call

            df = execute_fund_data_call(
                f"fund_portfolio_hold_em:{analysis_code}:{current_year}",
                lambda: ak.fund_portfolio_hold_em(symbol=analysis_code, date=current_year),
            )

            if df is None or df.empty:
                # 当前年份无数据，尝试上一年
                prev_year = str(datetime.now().year - 1)
                df = execute_fund_data_call(
                    f"fund_portfolio_hold_em:{analysis_code}:{prev_year}",
                    lambda: ak.fund_portfolio_hold_em(symbol=analysis_code, date=prev_year),
                )

            if df is None or df.empty:
                logger.info(f"[{analysis_code}] 未获取到披露持仓数据")
                return [], None

            # 只取最新一个季度的数据
            if '季度' in df.columns:
                latest_quarter = df['季度'].iloc[0]
                df = df[df['季度'] == latest_quarter]
                as_of_date = latest_quarter
            else:
                as_of_date = current_year

            items = []
            for _, row in df.iterrows():
                stock_code = str(row.get('股票代码', '')).strip()
                if not stock_code:
                    continue
                items.append({
                    "stock_code": stock_code,
                    "stock_name": str(row.get('股票名称', '')).strip() or None,
                    "weight": _safe_float(row.get('占净值比例')),
                    "rank": _safe_int(row.get('序号')),
                })

            logger.info(f"[{analysis_code}] 获取到 {len(items)} 条披露持仓，季度: {as_of_date}")
            return items, as_of_date

        except ImportError:
            logger.warning("akshare 未安装，无法获取持仓")
            return [], None
        except Exception as e:
            logger.warning(f"[{analysis_code}] 抓取披露持仓失败（fail-open）: {e}")
            return [], None

    @staticmethod
    def _build_unavailable_response(
        fund_code: str,
        fund_name: Optional[str],
        analysis_code: str,
    ) -> Dict[str, Any]:
        """构建 source_type='unavailable' 的响应。"""
        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "analysis_code": analysis_code,
            "analysis_name": None,
            "source_type": SOURCE_UNAVAILABLE,
            "completeness": COMPLETENESS_UNAVAILABLE,
            "as_of_date": None,
            "is_realtime": False,
            "items": [],
        }

    def _save_snapshot_rows(
        self,
        fund_code: str,
        fund_name: Optional[str],
        analysis_code: str,
        source_type: str,
        completeness: str,
        as_of_date: Optional[str],
        items: List[Dict[str, Any]],
        analysis_history_id: Optional[int] = None,
    ) -> None:
        """批量写入持仓快照行。"""
        if not items:
            return

        from sqlalchemy import insert

        rows = []
        now = datetime.now()
        for item in items:
            rows.append({
                "analysis_history_id": analysis_history_id,
                "fund_code": fund_code,
                "fund_name": fund_name,
                "analysis_code": analysis_code,
                "source_type": source_type,
                "completeness": completeness,
                "as_of_date": as_of_date,
                "stock_code": item["stock_code"],
                "stock_name": item.get("stock_name"),
                "weight": item.get("weight"),
                "rank": item.get("rank"),
                "fetched_at": now,
            })

        with self.db.session_scope() as session:
            session.execute(insert(FundHoldingsSnapshot), rows)
            logger.info(
                f"持仓快照已存储: fund_code={fund_code}, "
                f"analysis_code={analysis_code}, rows={len(rows)}, "
                f"history_id={analysis_history_id}"
            )

    def _load_snapshot_by_record_id(
        self,
        record_id: int,
    ) -> Optional[Dict[str, Any]]:
        """按 analysis_history_id 读取已有快照，并从 AnalysisHistory 补齐 analysis_name。"""
        from sqlalchemy import select

        with self.db.get_session() as session:
            results = session.execute(
                select(FundHoldingsSnapshot)
                .where(FundHoldingsSnapshot.analysis_history_id == record_id)
                .order_by(FundHoldingsSnapshot.rank)
            ).scalars().all()

            if not results:
                return None

            first = results[0]
            items = []
            for row in results:
                items.append({
                    "stock_code": row.stock_code,
                    "stock_name": row.stock_name,
                    "weight": row.weight,
                    "rank": row.rank,
                })

        # P2 fix: 从 AnalysisHistory 读取 analysis_name，保持与懒加载路径一致
        analysis_name = None
        record = self.db.get_analysis_history_by_id(record_id)
        if record:
            analysis_name = record.name

        return {
            "fund_code": first.fund_code,
            "fund_name": first.fund_name,
            "analysis_code": first.analysis_code,
            "analysis_name": analysis_name,
            "source_type": first.source_type,
            "completeness": first.completeness,
            "as_of_date": first.as_of_date,
            "is_realtime": False,
            "items": items,
        }


# ── 工具函数 ──

def _safe_float(value) -> Optional[float]:
    """安全转 float。"""
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    """安全转 int。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
