# -*- coding: utf-8 -*-
"""
全天候动态 ETF 组合 (5.2 估值温度策略) —— 每日计算与数据生成脚本
完全复用 dynamic_etf_tune5.2.py 的温度合成公式、中证500周期底部保护与防闪烁迟滞缓冲状态机。
输出：
  - docs/data.json : 供接口或外部读取的完整 JSON 数据
  - docs/data.js   : 供 docs/index.html 直接加载的 JS 数据包（支持本地双击打开与 GitHub Pages）
  - docs/latest_report.md : 最新一期策略状态 Markdown 摘要
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd


# ==============================================================================
# 1. 基础配置与 ETF 资产池定义（与 dynamic_etf_tune5.2.py 严格一致）
# ==============================================================================
ETF_META = {
    "hs300": {"code": "510300.XSHG", "name": "沪深300 ETF", "role": "大盘蓝筹"},
    "zz500": {"code": "510500.XSHG", "name": "中证500 ETF", "role": "中盘成长/周期"},
    "div_lowvol": {"code": "512890.XSHG", "name": "红利低波 ETF", "role": "现金流底仓"},
    "bond": {"code": "511010.XSHG", "name": "国债 ETF", "role": "股债跷跷板蓄水池"},
    "gold": {"code": "518880.XSHG", "name": "黄金 ETF", "role": "抗通胀/汇率底仓"},
}

NINE_GRID_RULES = [
    {
        "id": 1,
        "state_300": "冰点",
        "state_500": "冰点",
        "weights": {"hs300": 0.15, "zz500": 0.15, "div_lowvol": 0.15, "bond": 0.35, "gold": 0.20},
        "deposit_amt": 5000,
        "zone_msg": "【双重冰点】国债降至35%最低，双倍买入300与500",
    },
    {
        "id": 2,
        "state_300": "冰点",
        "state_500": "常温",
        "weights": {"hs300": 0.15, "zz500": 0.10, "div_lowvol": 0.15, "bond": 0.40, "gold": 0.20},
        "deposit_amt": 4000,
        "zone_msg": "【300冰点，500常温】重仓大盘",
    },
    {
        "id": 3,
        "state_300": "冰点",
        "state_500": "沸点",
        "weights": {"hs300": 0.15, "zz500": 0.05, "div_lowvol": 0.15, "bond": 0.45, "gold": 0.20},
        "deposit_amt": 3000,
        "zone_msg": "【300冰点，500沸点】极端跷跷板，国债保持45%",
    },
    {
        "id": 4,
        "state_300": "常温",
        "state_500": "冰点",
        "weights": {"hs300": 0.10, "zz500": 0.15, "div_lowvol": 0.15, "bond": 0.40, "gold": 0.20},
        "deposit_amt": 4000,
        "zone_msg": "【300常温，500冰点】重仓中盘",
    },
    {
        "id": 5,
        "state_300": "常温",
        "state_500": "常温",
        "weights": {"hs300": 0.10, "zz500": 0.10, "div_lowvol": 0.15, "bond": 0.45, "gold": 0.20},
        "deposit_amt": 3000,
        "zone_msg": "【双重常温】国债45%，均衡发展",
    },
    {
        "id": 6,
        "state_300": "常温",
        "state_500": "沸点",
        "weights": {"hs300": 0.10, "zz500": 0.05, "div_lowvol": 0.15, "bond": 0.50, "gold": 0.20},
        "deposit_amt": 2000,
        "zone_msg": "【300常温，500沸点】减仓中盘，回收国债",
    },
    {
        "id": 7,
        "state_300": "沸点",
        "state_500": "冰点",
        "weights": {"hs300": 0.05, "zz500": 0.15, "div_lowvol": 0.15, "bond": 0.45, "gold": 0.20},
        "deposit_amt": 3000,
        "zone_msg": "【300沸点，500冰点】极端跷跷板，国债保持45%",
    },
    {
        "id": 8,
        "state_300": "沸点",
        "state_500": "常温",
        "weights": {"hs300": 0.05, "zz500": 0.10, "div_lowvol": 0.15, "bond": 0.50, "gold": 0.20},
        "deposit_amt": 2000,
        "zone_msg": "【300沸点，500常温】减仓大盘，回收国债",
    },
    {
        "id": 9,
        "state_300": "沸点",
        "state_500": "沸点",
        "weights": {"hs300": 0.05, "zz500": 0.05, "div_lowvol": 0.15, "bond": 0.55, "gold": 0.20},
        "deposit_amt": 1000,
        "zone_msg": "【双重沸点】国债升至55%最高，全线防御",
    },
]


# ==============================================================================
# 2. 数据获取模块（带跨国网络自动重试机制）
# ==============================================================================
def retry_call(func, *args, retries=4, delay=4, **kwargs):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            print(f"[WARN] 第 {attempt}/{retries} 次调用 {func.__name__} 失败: {e}")
            if attempt < retries:
                time.sleep(delay * attempt)
    raise RuntimeError(f"调用 {func.__name__} 在重试 {retries} 次后仍然失败: {last_err}")


def fetch_bond_10y() -> pd.Series:
    """获取中国10年期国债到期收益率(%)"""
    print("正在拉取中国 10 年期国债到期收益率数据...")
    try:
        try:
            bond_df = retry_call(ak.bond_zh_us_yield_em, start_date="20050101")
        except TypeError:
            bond_df = retry_call(ak.bond_zh_us_yield_em)

        bond_df["日期"] = pd.to_datetime(bond_df["日期"])
        bond_df.set_index("日期", inplace=True)
        bond_df.sort_index(inplace=True)

        col_10y = "中国国债收益率10年"
        if col_10y not in bond_df.columns:
            candidates = [c for c in bond_df.columns if "中国" in str(c) and "10年" in str(c)]
            if candidates:
                col_10y = candidates[0]
            else:
                raise KeyError(f"未找到中国10年期国债收益率列，当前列: {list(bond_df.columns)}")

        s = pd.to_numeric(bond_df[col_10y], errors="coerce").ffill()
        return s.rename("bond_10y")
    except Exception as e:
        print(f"[ERROR] 获取10年期国债收益率失败: {e}")
        return pd.Series(dtype=float, name="bond_10y")


def fetch_index_data(symbol: str, bond_series: pd.Series) -> pd.DataFrame:
    """获取指数 PE / PB 并合成每日 ERP(%)"""
    print(f"正在拉取 [{symbol}] 历史 PE 与 PB 估值数据...")
    pe_df = retry_call(ak.stock_index_pe_lg, symbol=symbol)
    pe_df["日期"] = pd.to_datetime(pe_df["日期"])
    pe_df.set_index("日期", inplace=True)

    pb_df = retry_call(ak.stock_index_pb_lg, symbol=symbol)
    pb_df["日期"] = pd.to_datetime(pb_df["日期"])
    pb_df.set_index("日期", inplace=True)

    df = pd.merge(
        pe_df[["滚动市盈率"]],
        pb_df[["市净率"]],
        left_index=True,
        right_index=True,
        how="inner",
    )
    df.sort_index(inplace=True)

    if not bond_series.empty:
        df = df.join(bond_series, how="left")
        df["bond_10y"] = df["bond_10y"].ffill().bfill()
        df["ERP"] = (100.0 / df["滚动市盈率"]) - df["bond_10y"]
    else:
        df["bond_10y"] = float("nan")
        df["ERP"] = float("nan")

    return df


# ==============================================================================
# 3. 5.2 核心算法：综合温度计算 & 迟滞缓冲状态机
# ==============================================================================
def calc_composite_temperature_on_date(val_df: pd.DataFrame, eval_date: pd.Timestamp, index_type: str = "300"):
    """
    计算截至 eval_date 收盘时的指数综合估值温度 T (0.0 ~ 1.0) 及详细分位指标
    - PE / PB 采用滚动近 10 年窗口 (3650天)
    - ERP 采用滚动近 5 年窗口 (1825天)
    """
    if val_df.empty:
        return None

    history_data = val_df[val_df.index <= eval_date]
    if len(history_data) < 60:
        return None

    ten_years_ago = eval_date - pd.Timedelta(days=3650)
    five_years_ago = eval_date - pd.Timedelta(days=1825)

    rolling_10y = history_data[history_data.index >= ten_years_ago]
    rolling_5y = history_data[history_data.index >= five_years_ago]

    if len(rolling_10y) < 12:
        return None

    latest = rolling_10y.iloc[-1]
    current_pe = float(latest["滚动市盈率"])
    current_pb = float(latest["市净率"])
    current_bond_10y = float(latest["bond_10y"]) if pd.notna(latest.get("bond_10y")) else None

    pe_pct = float((rolling_10y["滚动市盈率"] <= current_pe).sum() / len(rolling_10y))
    pb_pct = float((rolling_10y["市净率"] <= current_pb).sum() / len(rolling_10y))

    erp_valid = rolling_5y["ERP"].dropna()
    if len(erp_valid) >= 12 and pd.notna(latest.get("ERP")):
        current_erp = float(latest["ERP"])
        erp_pct = float((erp_valid <= current_erp).sum() / len(erp_valid))
        erp_temp = 1.0 - erp_pct
    else:
        current_erp = None
        erp_pct = None
        erp_temp = (pe_pct + pb_pct) / 2.0

    cyclical_veto = False
    if index_type == "300":
        # 沪深300综合温度：50% PE分位 + 20% PB分位 + 30% (1 - ERP分位)
        raw_temp = 0.50 * pe_pct + 0.20 * pb_pct + 0.30 * erp_temp
        temp = raw_temp
    else:
        # 中证500综合温度：30% PE分位 + 40% PB分位 + 30% (1 - ERP分位)
        raw_temp = 0.30 * pe_pct + 0.40 * pb_pct + 0.30 * erp_temp
        temp = raw_temp
        # 【中证500周期股盈利失真保护】：当 PE 分位 > 50% 但 PB 分位 <= 15% 时，一票否决 PE 虚高
        if pe_pct > 0.50 and pb_pct <= 0.15:
            temp = min(temp, pb_pct)
            cyclical_veto = True

    return {
        "temp": float(temp),
        "raw_temp": float(raw_temp),
        "cyclical_veto": cyclical_veto,
        "pe": current_pe,
        "pb": current_pb,
        "erp": current_erp,
        "bond_10y": current_bond_10y,
        "pe_pct": pe_pct,
        "pb_pct": pb_pct,
        "erp_pct": erp_pct,
        "erp_temp": float(erp_temp),
    }


def update_state_with_buffer(metrics, prev_state: str) -> str:
    """
    带防闪烁迟滞缓冲带（Hysteresis Buffer）的状态机转换规则：
    - 冰点触发线：<= 20% (0.20)
    - 冰点缓冲带：20% ~ 30%（原为冰点则保持冰点，突破 30% 才退回常温；原为常温则保持常温）
    - 标准常温区：30% ~ 70%（锁定常温）
    - 沸点缓冲带：70% ~ 80%（原为沸点则保持沸点，跌破 70% 才退回常温；原为常温则保持常温）
    - 沸点触发线：>= 80% (0.80)
    """
    if metrics is None:
        return "数据异常"

    t = metrics["temp"]

    if t <= 0.20:
        return "冰点"
    elif t >= 0.80:
        return "沸点"
    elif 0.30 < t < 0.70:
        return "常温"
    elif 0.20 < t <= 0.30:
        return "冰点" if prev_state == "冰点" else "常温"
    else:  # 0.70 <= t < 0.80
        return "沸点" if prev_state == "沸点" else "常温"


def describe_buffer_status(temp: float, current_state: str) -> dict:
    """生成用于前端展示的缓冲区状态与下一变盘点说明"""
    t_deg = temp * 100.0
    in_ice_buffer = 0.20 < temp <= 0.30
    in_boil_buffer = 0.70 <= temp < 0.80
    in_buffer = in_ice_buffer or in_boil_buffer

    if current_state == "冰点":
        if in_ice_buffer:
            buffer_tag = "处于 20°C~30°C 冰点缓冲带（保持冰点）"
        else:
            buffer_tag = "处于 ≤20°C 深度冰点区"
        next_trigger = f"需回暖突破 30.0°C（还差 +{30.0 - t_deg:.1f}°C）才退出【冰点】转入【常温】"
    elif current_state == "沸点":
        if in_boil_buffer:
            buffer_tag = "处于 70°C~80°C 沸点缓冲带（保持沸点）"
        else:
            buffer_tag = "处于 ≥80°C 深度沸点区"
        next_trigger = f"需降温跌破 70.0°C（还差 -{t_deg - 70.0:.1f}°C）才退出【沸点】转入【常温】"
    else:  # 常温
        if in_ice_buffer:
            buffer_tag = "处于 20°C~30°C 缓冲带（未破 20°C 维持常温）"
        elif in_boil_buffer:
            buffer_tag = "处于 70°C~80°C 缓冲带（未破 80°C 维持常温）"
        else:
            buffer_tag = "处于 30°C~70°C 标准常温核心区"
        to_ice = t_deg - 20.0
        to_boil = 80.0 - t_deg
        next_trigger = f"距进入【冰点】(≤20°C) 差 -{to_ice:.1f}°C | 距进入【沸点】(≥80°C) 差 +{to_boil:.1f}°C"

    return {
        "in_buffer": in_buffer,
        "buffer_tag": buffer_tag,
        "next_trigger": next_trigger,
    }


def match_nine_grid(state_300: str, state_500: str) -> dict:
    for rule in NINE_GRID_RULES:
        if rule["state_300"] == state_300 and rule["state_500"] == state_500:
            return rule
    # 默认兜底：第 5 格（双重常温）
    return NINE_GRID_RULES[4]


# ==============================================================================
# 4. 全历史序列滚动推演与文件导出
# ==============================================================================
def main():
    bond_10y_series = fetch_bond_10y()
    val_df_300 = fetch_index_data("沪深300", bond_10y_series)
    val_df_500 = fetch_index_data("中证500", bond_10y_series)

    if val_df_300.empty or val_df_500.empty:
        raise RuntimeError("沪深300或中证500估值数据为空，无法计算策略状态。")

    # 取两个指数共同交易日，从 2018-01-01 起算（并在 2020-01-01 对齐回测起点）
    common_dates = val_df_300.index.intersection(val_df_500.index).sort_values()
    start_calc_date = pd.Timestamp("2018-01-01")
    eval_dates = [d for d in common_dates if d >= start_calc_date]

    state_300 = "常温"
    state_500 = "常温"
    reset_at_2020_done = False

    history = {
        "dates": [],
        "temp_300": [],
        "temp_500": [],
        "state_300": [],
        "state_500": [],
        "pe_300": [],
        "pb_300": [],
        "erp_300": [],
        "pe_pct_300": [],
        "pb_pct_300": [],
        "erp_pct_300": [],
        "pe_500": [],
        "pb_500": [],
        "erp_500": [],
        "pe_pct_500": [],
        "pb_pct_500": [],
        "erp_pct_500": [],
        "bond_10y": [],
        "deposit_amt": [],
        "zone_id": [],
        "w_hs300": [],
        "w_zz500": [],
        "w_div": [],
        "w_bond": [],
        "w_gold": [],
    }

    latest_m300 = None
    latest_m500 = None
    latest_rule = None
    latest_date_str = None

    print(f"正在从 {eval_dates[0].strftime('%Y-%m-%d')} 至 {eval_dates[-1].strftime('%Y-%m-%d')} 逐日推演 5.2 状态机...")

    for d in eval_dates:
        # 与 2020 年开始的 RQAlpha 回测初始状态严格对齐
        if not reset_at_2020_done and d >= pd.Timestamp("2020-01-01"):
            state_300 = "常温"
            state_500 = "常温"
            reset_at_2020_done = True

        m300 = calc_composite_temperature_on_date(val_df_300, d, index_type="300")
        m500 = calc_composite_temperature_on_date(val_df_500, d, index_type="500")
        if m300 is None or m500 is None:
            continue

        new_s300 = update_state_with_buffer(m300, state_300)
        new_s500 = update_state_with_buffer(m500, state_500)
        if new_s300 != "数据异常":
            state_300 = new_s300
        if new_s500 != "数据异常":
            state_500 = new_s500

        rule = match_nine_grid(state_300, state_500)
        d_str = d.strftime("%Y-%m-%d")

        history["dates"].append(d_str)
        history["temp_300"].append(round(m300["temp"] * 100, 2))
        history["temp_500"].append(round(m500["temp"] * 100, 2))
        history["state_300"].append(state_300)
        history["state_500"].append(state_500)

        history["pe_300"].append(round(m300["pe"], 2))
        history["pb_300"].append(round(m300["pb"], 2))
        history["erp_300"].append(round(m300["erp"], 2) if m300["erp"] is not None else None)
        history["pe_pct_300"].append(round(m300["pe_pct"] * 100, 1))
        history["pb_pct_300"].append(round(m300["pb_pct"] * 100, 1))
        history["erp_pct_300"].append(round(m300["erp_pct"] * 100, 1) if m300["erp_pct"] is not None else None)

        history["pe_500"].append(round(m500["pe"], 2))
        history["pb_500"].append(round(m500["pb"], 2))
        history["erp_500"].append(round(m500["erp"], 2) if m500["erp"] is not None else None)
        history["pe_pct_500"].append(round(m500["pe_pct"] * 100, 1))
        history["pb_pct_500"].append(round(m500["pb_pct"] * 100, 1))
        history["erp_pct_500"].append(round(m500["erp_pct"] * 100, 1) if m500["erp_pct"] is not None else None)

        history["bond_10y"].append(round(m300["bond_10y"], 3) if m300["bond_10y"] is not None else None)
        history["deposit_amt"].append(rule["deposit_amt"])
        history["zone_id"].append(rule["id"])

        w = rule["weights"]
        history["w_hs300"].append(round(w["hs300"] * 100, 1))
        history["w_zz500"].append(round(w["zz500"] * 100, 1))
        history["w_div"].append(round(w["div_lowvol"] * 100, 1))
        history["w_bond"].append(round(w["bond"] * 100, 1))
        history["w_gold"].append(round(w["gold"] * 100, 1))

        latest_m300 = m300
        latest_m500 = m500
        latest_rule = rule
        latest_date_str = d_str

    if latest_m300 is None or latest_m500 is None or latest_rule is None:
        raise RuntimeError("未能计算出有效估值状态。")

    tz_bj = timezone(timedelta(hours=8))
    updated_at_str = datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S (北京时间)")

    buf_300 = describe_buffer_status(latest_m300["temp"], state_300)
    buf_500 = describe_buffer_status(latest_m500["temp"], state_500)

    payload = {
        "strategy_version": "5.2 (ERP + 差异化权重 + 迟滞缓冲区)",
        "updated_at": updated_at_str,
        "latest_date": latest_date_str,
        "bond_10y": round(latest_m300["bond_10y"], 3) if latest_m300["bond_10y"] is not None else None,
        "etf_meta": ETF_META,
        "current": {
            "zone_id": latest_rule["id"],
            "zone_msg": latest_rule["zone_msg"],
            "deposit_amt": latest_rule["deposit_amt"],
            "state_300": state_300,
            "state_500": state_500,
            "weights": {k: round(v * 100, 1) for k, v in latest_rule["weights"].items()},
            "hs300": {
                "name": "沪深300",
                "etf_code": ETF_META["hs300"]["code"],
                "state": state_300,
                "temp": round(latest_m300["temp"] * 100, 2),
                "raw_temp": round(latest_m300["raw_temp"] * 100, 2),
                "cyclical_veto": False,
                "pe": round(latest_m300["pe"], 2),
                "pb": round(latest_m300["pb"], 2),
                "erp": round(latest_m300["erp"], 2) if latest_m300["erp"] is not None else None,
                "pe_pct": round(latest_m300["pe_pct"] * 100, 1),
                "pb_pct": round(latest_m300["pb_pct"] * 100, 1),
                "erp_pct": round(latest_m300["erp_pct"] * 100, 1) if latest_m300["erp_pct"] is not None else None,
                "erp_temp": round(latest_m300["erp_temp"] * 100, 1),
                "formula_desc": "50% PE分位 + 20% PB分位 + 30% (100% - ERP分位)",
                **buf_300,
            },
            "zz500": {
                "name": "中证500",
                "etf_code": ETF_META["zz500"]["code"],
                "state": state_500,
                "temp": round(latest_m500["temp"] * 100, 2),
                "raw_temp": round(latest_m500["raw_temp"] * 100, 2),
                "cyclical_veto": latest_m500["cyclical_veto"],
                "pe": round(latest_m500["pe"], 2),
                "pb": round(latest_m500["pb"], 2),
                "erp": round(latest_m500["erp"], 2) if latest_m500["erp"] is not None else None,
                "pe_pct": round(latest_m500["pe_pct"] * 100, 1),
                "pb_pct": round(latest_m500["pb_pct"] * 100, 1),
                "erp_pct": round(latest_m500["erp_pct"] * 100, 1) if latest_m500["erp_pct"] is not None else None,
                "erp_temp": round(latest_m500["erp_temp"] * 100, 1),
                "formula_desc": "30% PE分位 + 40% PB分位 + 30% (100% - ERP分位)",
                **buf_500,
            },
        },
        "nine_grid": [
            {
                **r,
                "weights_pct": {k: round(v * 100, 1) for k, v in r["weights"].items()},
                "active": r["id"] == latest_rule["id"],
            }
            for r in NINE_GRID_RULES
        ],
        "history": history,
    }

    docs_dir = Path(__file__).resolve().parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. 写入 docs/data.json
    json_path = docs_dir / "data.json"
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_str, encoding="utf-8")

    # 2. 写入 docs/data.js (供 HTML 直接通过 <script src="./data.js"> 无跨域加载)
    js_path = docs_dir / "data.js"
    js_content = f"window.STRATEGY_DATA = {json.dumps(payload, ensure_ascii=False)};\n"
    js_path.write_text(js_content, encoding="utf-8")

    # 3. 写入 docs/latest_report.md (方便在 GitHub 仓库或 Action Summary 中直接阅读)
    c = payload["current"]
    h300 = c["hs300"]
    z500 = c["zz500"]
    w = c["weights"]
    md_lines = [
        f"# 📊 5.2 估值温度策略日报（{latest_date_str}）",
        f"",
        f"- **更新时间**：`{updated_at_str}`",
        f"- **10年期国债收益率**：`{payload['bond_10y']}%`",
        f"- **当前九宫格状态**：**{c['zone_msg']}**（第 `{c['zone_id']}` 格）",
        f"- **当月建议定投金额**：**`{c['deposit_amt']} 元`**（基准 3000 元）",
        f"",
        f"## 🌡️ 宽基指数估值温度拆解",
        f"",
        f"| 指数 | 当前状态 | 综合温度 | PE-TTM (10年分位) | PB (10年分位) | ERP股债利差 (5年分位) | 缓冲带与变盘距离 |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        f"| **沪深300** | **{h300['state']}** | **{h300['temp']}°C** | {h300['pe']} ({h300['pe_pct']}%) | {h300['pb']} ({h300['pb_pct']}%) | {h300['erp']}% ({h300['erp_pct']}%) | {h300['next_trigger']} |",
        f"| **中证500** | **{z500['state']}** | **{z500['temp']}°C** | {z500['pe']} ({z500['pe_pct']}%) | {z500['pb']} ({z500['pb_pct']}%) | {z500['erp']}% ({z500['erp_pct']}%) | {z500['next_trigger']} |",
        f"",
        f"## 🎯 目标资产配置比例",
        f"",
        f"| 资产类别 | ETF 代码 | 目标权重 | 当月定投拆分参考 ({c['deposit_amt']}元) |",
        f"| :--- | :---: | :---: | :---: |",
        f"| **沪深300 ETF** | `510300.XSHG` | **{w['hs300']}%** | {round(c['deposit_amt'] * w['hs300'] / 100)} 元 |",
        f"| **中证500 ETF** | `510500.XSHG` | **{w['zz500']}%** | {round(c['deposit_amt'] * w['zz500'] / 100)} 元 |",
        f"| **红利低波 ETF** | `512890.XSHG` | **{w['div_lowvol']}%** | {round(c['deposit_amt'] * w['div_lowvol'] / 100)} 元 |",
        f"| **国债 ETF** | `511010.XSHG` | **{w['bond']}%** | {round(c['deposit_amt'] * w['bond'] / 100)} 元 |",
        f"| **黄金 ETF** | `518880.XSHG` | **{w['gold']}%** | {round(c['deposit_amt'] * w['gold'] / 100)} 元 |",
        f"",
    ]
    report_path = docs_dir / "latest_report.md"
    report_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("=" * 65)
    print(f"计算完成！最新估值日期: {latest_date_str}")
    print(
        f"当期温度 -> 300[{state_300}]: 温度={h300['temp']}°C "
        f"(PE分位={h300['pe_pct']}%, PB分位={h300['pb_pct']}%, ERP={h300['erp']}%/分位={h300['erp_pct']}%) | "
        f"500[{state_500}]: 温度={z500['temp']}°C "
        f"(PE分位={z500['pe_pct']}%, PB分位={z500['pb_pct']}%, ERP={z500['erp']}%/分位={z500['erp_pct']}%)"
    )
    print(f"状态: {c['zone_msg']} | 建议入金: {c['deposit_amt']} 元")
    print(f"已输出文件:\n  - {json_path}\n  - {js_path}\n  - {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
