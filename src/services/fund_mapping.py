# -*- coding: utf-8 -*-
"""
基金代码 → ETF代码 自动映射服务

场外基金没有实时行情、K线、MACD等数据，无法直接用趋势策略分析。
本服务将场外基金代码自动映射到跟踪同一指数的场内ETF，用ETF数据进行分析。

流程：
1. 判断输入代码是否为场外基金
2. 通过 akshare 获取基金的跟踪指数/业绩基准
3. 在所有场内ETF中匹配同一指数
4. 返回最优ETF代码（按规模/流动性排序）
"""

import logging
import re
import time
import threading
from typing import List, Optional, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)


# 单次基金映射查询超时（秒），避免前端请求被外部接口拖死
FUND_MAPPING_TIMEOUT_SECONDS = 8

# 模块级线程池（单 worker），避免每次查询都创建销毁
_mapping_executor = ThreadPoolExecutor(max_workers=1)

# 简易 TTL 缓存：{fund_code: (result, timestamp)}
_mapping_cache: Dict[str, Tuple[Optional[Tuple[str, str, str]], float]] = {}
_mapping_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 86400  # 24 小时


# 常见场外基金 → ETF 静态映射（作为API查询的兜底）
FUND_ETF_STATIC_MAP: Dict[str, str] = {
    # 芯片/半导体
    "017811": "516980",  # 景顺长城国证机器人产业ETF → 芯片ETF
    "012414": "516980",
    "007300": "159995",  # 芯片ETF
    "007301": "159995",
    # 新能源
    "012035": "516580",  # 新能源ETF
    "012036": "516580",
    # 医药
    "006002": "512010",  # 医药ETF
    "006003": "512010",
    # 消费
    "001632": "159928",  # 消费ETF
    "001633": "159928",
    # 白酒
    "003095": "512690",  # 白酒ETF
    # 军工
    "004224": "512660",  # 军工ETF
    "004225": "512660",
    # 沪深300
    "110020": "510300",  # 沪深300ETF
    "000051": "510300",
    # 中证500
    "160119": "510500",  # 中证500ETF
    "000962": "510500",
    # 创业板
    "110026": "159915",  # 创业板ETF
    "001593": "159915",
}

# 指数关键词 → ETF代码映射（用于模糊匹配）
INDEX_ETF_MAP: Dict[str, str] = {
    "恒生科技": "513180",
    "恒生指数": "159920",
    "沪深300": "510300",
    "中证500": "510500",
    "中证1000": "560010",
    "上证50": "510050",
    "创业板": "159915",
    "科创50": "588000",
    "纳斯达克": "513100",
    "标普500": "513500",
    "芯片": "516980",
    "半导体": "512480",
    "新能源": "516580",
    "光伏": "515790",
    "医药": "512010",
    "生物医药": "512290",
    "白酒": "512690",
    "消费": "159928",
    "食品饮料": "515170",
    "军工": "512660",
    "国防军工": "512660",
    "银行": "512800",
    "证券": "512880",
    "券商": "512880",
    "保险": "512070",
    "房地产": "512200",
    "煤炭": "515220",
    "钢铁": "515210",
    "有色金属": "159880",
    "有色": "159880",
    "电力设备": "159559",
    "电网设备": "159559",
    "电力": "159559",
    "汽车": "516110",
    "新能源汽车": "515030",
    "人工智能": "515070",
    "大数据": "515400",
    "云计算": "516510",
    "5G": "515050",
    "通信": "515880",
    "游戏": "516010",
    "传媒": "512980",
    "农业": "159825",
    "基建": "516950",
    "碳中和": "516070",
    "机器人": "562500",
    "家电": "159996",
}


def is_otc_fund_code(code: str) -> bool:
    """
    判断是否为场外基金代码（非股票、非ETF）

    场外基金代码规律：
    - 6位数字
    - 不属于已知的股票/ETF代码段

    已知股票/ETF代码段：
    - 60xxxx: 上证主板
    - 00xxxx: 深证主板 (000-004)
    - 002xxx: 中小板
    - 300xxx, 301xxx: 创业板
    - 688xxx: 科创板
    - 51xxxx, 56xxxx: 上证ETF
    - 15xxxx, 16xxxx: 深证ETF
    """
    if not re.match(r'^\d{6}$', code):
        return False

    # 股票代码段
    stock_prefixes = [
        '600', '601', '603', '605',  # 上证主板
        '000', '001', '002', '003',  # 深证主板/中小板
        '300', '301',                 # 创业板
        '688', '689',                 # 科创板
        '830', '831', '870', '871',   # 北交所/新三板
        '920',                         # 存托凭证 CDR
        '510', '511', '512', '513', '515', '516', '517', '518', '560', '561', '562', '563',  # 上证ETF
        '159', '150', '160', '161', '162', '163', '164',  # 深证ETF/LOF
    ]

    prefix3 = code[:3]
    if prefix3 in stock_prefixes:
        return False

    # 如果不属于任何已知股票/ETF代码段，认为是场外基金
    return True


def get_fund_etf_mapping(fund_code: str) -> Optional[Tuple[str, str, str]]:
    """
    将场外基金代码映射到对应的场内ETF（带 TTL 缓存）

    Args:
        fund_code: 场外基金代码

    Returns:
        (etf_code, fund_name, etf_name) 或 None
    """
    # 0. 检查 TTL 缓存
    now = time.monotonic()
    with _mapping_cache_lock:
        if fund_code in _mapping_cache:
            cached_result, cached_at = _mapping_cache[fund_code]
            if now - cached_at < _CACHE_TTL_SECONDS:
                return cached_result
            del _mapping_cache[fund_code]

    # 1. 先查静态映射
    if fund_code in FUND_ETF_STATIC_MAP:
        etf_code = FUND_ETF_STATIC_MAP[fund_code]
        logger.info(f"[基金映射] {fund_code} -> {etf_code} (静态映射)")
        result = etf_code, f"基金{fund_code}", f"ETF{etf_code}"
        with _mapping_cache_lock:
            _mapping_cache[fund_code] = (result, now)
        return result

    # 2. 通过 akshare API 查询（使用模块级线程池，带超时降级）
    try:
        future = _mapping_executor.submit(_query_fund_mapping_via_akshare, fund_code)
        result = future.result(timeout=FUND_MAPPING_TIMEOUT_SECONDS)
        with _mapping_cache_lock:
            _mapping_cache[fund_code] = (result, now)
        return result
    except FutureTimeoutError:
        logger.warning(
            f"[基金映射] {fund_code} 查询超时({FUND_MAPPING_TIMEOUT_SECONDS}s)，回退直接分析原基金代码"
        )
        return None
    except Exception as e:
        logger.warning(f"[基金映射] akshare查询失败: {e}")
        return None


def _query_fund_mapping_via_akshare(fund_code: str) -> Optional[Tuple[str, str, str]]:
    """通过 akshare API 查询基金信息并匹配ETF"""
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare 未安装")
        return None

    # Step 1: 获取基金基本信息
    fund_name = ""
    benchmark = ""

    try:
        fund_info = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if fund_info is not None and not fund_info.empty:
            info_dict = {}
            for _, row in fund_info.iterrows():
                key = str(row.iloc[0]).strip() if len(row) > 0 else ""
                val = str(row.iloc[1]).strip() if len(row) > 1 else ""
                info_dict[key] = val

            fund_name = info_dict.get("基金全称", info_dict.get("基金简称", f"基金{fund_code}"))
            benchmark = info_dict.get("业绩比较基准", "")
            logger.info(f"[基金映射] {fund_code} 名称={fund_name}, 基准={benchmark}")
    except Exception as e:
        logger.warning(f"[基金映射] 获取基金信息失败: {e}")
        # 尝试备用方法
        try:
            fund_list = _get_fund_name_list()
            if fund_code in fund_list:
                fund_name = fund_list[fund_code]
        except Exception:
            pass

    if not fund_name:
        fund_name = f"基金{fund_code}"

    # Step 2: 优先从基金名称中匹配（名称比业绩基准更精确）
    for keyword, etf_code in INDEX_ETF_MAP.items():
        if keyword in fund_name:
            logger.info(f"[基金映射] {fund_code}({fund_name}) -> {etf_code} (基金名称匹配: {keyword})")
            return etf_code, fund_name, f"ETF{etf_code}"

    # Step 3: 从业绩基准中提取主要跟踪指数（按权重排序）
    if benchmark:
        # 解析业绩基准中的指数及权重，如 "中证半导体指数*70%+恒生指数*10%+..."
        benchmark_parts = _parse_benchmark_weights(benchmark)
        # 按权重从高到低匹配
        for index_name, weight in benchmark_parts:
            for keyword, etf_code in INDEX_ETF_MAP.items():
                if keyword in index_name:
                    logger.info(f"[基金映射] {fund_code}({fund_name}) -> {etf_code} (业绩基准匹配: {keyword}, 权重{weight}%)")
                    return etf_code, fund_name, f"ETF{etf_code}"

    # Step 4: 如果关键词匹配失败，尝试在ETF列表中搜索
    try:
        etf_list = ak.fund_etf_spot_em()
        if etf_list is not None and not etf_list.empty:
            # 从基金名称中提取可能的指数名
            name_keywords = re.findall(r'[\u4e00-\u9fff]+', fund_name)
            for kw in name_keywords:
                if len(kw) >= 2 and kw not in ['基金', '指数', '联接', '增强', 'LOF']:
                    matches = etf_list[etf_list['名称'].str.contains(kw, na=False)]
                    if not matches.empty:
                        # 取成交额最大的ETF
                        best = matches.sort_values('成交额', ascending=False).iloc[0]
                        etf_code = str(best['代码'])
                        etf_name = str(best['名称'])
                        logger.info(f"[基金映射] {fund_code}({fund_name}) -> {etf_code}({etf_name}) (ETF列表匹配: {kw})")
                        return etf_code, fund_name, etf_name
    except Exception as e:
        logger.warning(f"[基金映射] ETF列表搜索失败: {e}")

    logger.warning(f"[基金映射] {fund_code}({fund_name}) 未找到对应ETF")
    return None




def _parse_benchmark_weights(benchmark: str) -> List[Tuple[str, float]]:
    """
    解析业绩基准字符串，提取各指数及其权重，按权重从高到低排序。

    示例输入:
      "中证全指半导体产品与设备指数收益率×70%+恒生指数收益率×10%+中债-综合指数收益率×20%"
      "沪深300指数*80%+中证综合债券指数*20%"

    返回: [("中证全指半导体产品与设备指数收益率", 70.0), ("中债-综合指数收益率", 20.0), ("恒生指数收益率", 10.0)]
    """
    results = []

    # 按 + 分割各组成部分
    parts = re.split(r'[+＋]', benchmark)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 匹配 "指数名称*权重%" 或 "指数名称×权重%" 格式
        match = re.match(r'(.+?)\s*[*×✕]\s*([\d.]+)\s*%', part)
        if match:
            index_name = match.group(1).strip()
            weight = float(match.group(2))
            results.append((index_name, weight))
        else:
            # 无法解析权重的部分，给默认权重0
            results.append((part, 0.0))

    # 按权重从高到低排序
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# 基金名称列表缓存
_fund_name_cache: Optional[Dict[str, str]] = None
_fund_name_cache_time: float = 0.0


def _get_fund_name_list() -> Dict[str, str]:
    """获取基金名称列表（24h TTL 缓存）"""
    global _fund_name_cache, _fund_name_cache_time
    now = time.monotonic()
    if _fund_name_cache is not None and now - _fund_name_cache_time < _CACHE_TTL_SECONDS:
        return _fund_name_cache
    try:
        import akshare as ak
        df = ak.fund_name_em()
        if df is not None and not df.empty:
            _fund_name_cache = dict(zip(df['基金代码'].astype(str), df['基金简称']))
            _fund_name_cache_time = now
            return _fund_name_cache
    except Exception:
        pass
    return {}


def resolve_code(code: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    统一代码解析入口

    如果是场外基金代码，自动映射到ETF；否则原样返回。

    Args:
        code: 用户输入的代码（可能是股票、ETF、或场外基金）

    Returns:
        (analysis_code, original_fund_name, mapping_note)
        - analysis_code: 用于分析的代码（ETF或股票）
        - original_fund_name: 原始基金名称（非基金则为None）
        - mapping_note: 映射说明（如 "017811 → 516980 芯片ETF"）
    """
    if not is_otc_fund_code(code):
        return code, None, None

    logger.info(f"[代码解析] 检测到场外基金代码: {code}，开始查找对应ETF...")

    result = get_fund_etf_mapping(code)
    if result:
        etf_code, fund_name, etf_name = result
        note = f"场外基金 {code}({fund_name}) → 对应ETF {etf_code}({etf_name})"
        logger.info(f"[代码解析] {note}")
        return etf_code, fund_name, note

    logger.warning(f"[代码解析] 基金 {code} 未找到对应ETF，将尝试直接分析")
    return code, None, None
