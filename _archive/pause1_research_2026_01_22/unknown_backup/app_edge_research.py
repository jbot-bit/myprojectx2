from __future__ import annotations

import io
from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import query_engine as qe


st.set_page_config(page_title="Dashboard A — ORB Edge Research", layout="wide")


@st.cache_resource(show_spinner=False)
def get_connection():
    return qe.get_connection("gold.db")


@st.cache_data(show_spinner=False)
def load_metadata() -> Dict[str, Any]:
    return qe.fetch_filter_metadata(get_connection())


@st.cache_data(show_spinner=False)
def load_headline_stats(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> Dict[str, Any]:
    return qe.headline_stats_with_strategy(get_connection(), filters, strategy)


@st.cache_data(show_spinner=False)
def load_equity_curve(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> pd.DataFrame:
    return qe.equity_curve_with_strategy(get_connection(), filters, strategy)


@st.cache_data(show_spinner=False)
def load_histogram(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> pd.DataFrame:
    return qe.histogram_with_strategy(get_connection(), filters, strategy)


@st.cache_data(show_spinner=False)
def load_heatmap(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> pd.DataFrame:
    return qe.heatmap_with_strategy(get_connection(), filters, strategy)


@st.cache_data(show_spinner=False)
def load_drilldown(
    filters_key: Tuple[Any, ...],
    strategy_key: Tuple[Any, ...],
    filters: qe.Filters,
    strategy: qe.StrategyConfig,
    limit: Optional[int],
    order: str,
) -> pd.DataFrame:
    return qe.drilldown_with_strategy(get_connection(), filters, strategy, limit=limit, order=order)


@st.cache_data(show_spinner=False)
def load_drilldown_full(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> pd.DataFrame:
    return qe.drilldown_full_with_strategy(get_connection(), filters, strategy, order="chronological")


@st.cache_data(show_spinner=False)
def load_funnel(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
) -> Dict[str, int]:
    return qe.entry_funnel(get_connection(), filters, strategy)


def _sanitize_for_display(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)


def _date_bounds(metadata: Dict[str, Any]) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    min_date = pd.to_datetime(metadata.get("min_date")) if metadata.get("min_date") else None
    max_date = pd.to_datetime(metadata.get("max_date")) if metadata.get("max_date") else None
    return min_date, max_date


def _set_defaults(metadata: Dict[str, Any]) -> None:
    min_date, max_date = _date_bounds(metadata)
    defaults = {
        "date_range": (min_date.date(), max_date.date()) if min_date and max_date else (None, None),
        "orb_times": list(qe.ORB_TIMES),
        "break_dir": "ANY",
        "outcomes": list(qe.OUTCOME_OPTIONS),
        "asia_type": "ANY",
        "london_type": "ANY",
        "preny_type": "ANY",
        "include_null_asia": True,
        "include_null_london": True,
        "include_null_preny": True,
        "enable_atr": False,
        "atr_range": (
            float(metadata["min_atr"]) if metadata.get("min_atr") is not None else 0.0,
            float(metadata["max_atr"]) if metadata.get("max_atr") is not None else 0.0,
        ),
        "enable_asia_range": False,
        "asia_range_values": (
            float(metadata["min_asia_range"]) if metadata.get("min_asia_range") is not None else 0.0,
            float(metadata["max_asia_range"]) if metadata.get("max_asia_range") is not None else 0.0,
        ),
        "top_n_enabled": False,
        "top_n_value": 100,
        "search_mode": "Simple",
        "simple_level_basis": "ORB boundary (High/Low)",
        "simple_entry_option": "First 1m close beyond level",
        "simple_retest": False,
        "simple_retest_type": "Touch level",
        "simple_pierce_ticks": 2,
        "simple_rejection": "1m rejection close in breakout direction",
        "simple_max_stop": "",
        "simple_cutoff": "",
        "simple_one_trade": True,
        "adv_preset": list(qe.PRESETS.keys())[0],
        "adv_level_basis": qe.default_strategy().level_basis,
        "adv_entry_model": qe.default_strategy().entry_model,
        "adv_confirm_closes": qe.default_strategy().confirm_closes,
        "adv_retest_required": qe.default_strategy().retest_required,
        "adv_retest_rule": qe.default_strategy().retest_rule,
        "adv_pierce_ticks": qe.default_strategy().pierce_ticks or 0,
        "adv_rejection_tf": qe.default_strategy().rejection_tf,
        "adv_max_stop": "",
        "adv_cutoff": "",
        "adv_one_trade": qe.default_strategy().one_trade_per_orb,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset_all(metadata: Dict[str, Any]) -> None:
    st.session_state.clear()
    _set_defaults(metadata)
    st.experimental_rerun()


def _parse_optional_int(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        st.warning(f"Could not parse integer: {value}")
        return None


def build_filters_and_strategy(metadata: Dict[str, Any]) -> Tuple[Optional[qe.Filters], qe.StrategyConfig]:
    min_date, max_date = _date_bounds(metadata)
    if not min_date or not max_date:
        st.error("No data available in v_orb_trades.")
        return None, qe.default_strategy()

    with st.sidebar:
        st.header("Filters")
        search_mode = st.radio("Search mode", ["Simple", "Advanced"], key="search_mode")
        col_reset, _ = st.columns([1, 3])
        if col_reset.button("Reset filters"):
            _reset_all(metadata)

        date_range = st.date_input(
            "Date range",
            min_value=min_date.date(),
            max_value=max_date.date(),
            format="YYYY-MM-DD",
            key="date_range",
        )
        start_date, end_date = date_range if isinstance(date_range, tuple) else (date_range, date_range)

        orb_times = st.multiselect(
            "ORB Time",
            qe.ORB_TIMES,
            key="orb_times",
            help="Default includes all ORB times.",
        )
        break_dir = st.selectbox(
            "Direction",
            qe.BREAK_DIR_OPTIONS,
            key="break_dir",
        )
        outcomes = st.multiselect(
            "Outcome",
            qe.OUTCOME_OPTIONS,
            key="outcomes",
            help="Keep NO_TRADE selected to include all opportunities.",
        )

        with st.expander("Session codes", expanded=False):
            asia_codes = ["ANY"] + metadata.get("asia_type_codes", [])
            london_codes = ["ANY"] + metadata.get("london_type_codes", [])
            preny_codes = ["ANY"] + metadata.get("pre_ny_type_codes", [])

            asia_type = st.selectbox("Asia type code", asia_codes, key="asia_type")
            if asia_type != "ANY":
                st.checkbox("Include NULL Asia codes", value=True, key="include_null_asia", help="Default ON")
            london_type = st.selectbox("London type code", london_codes, key="london_type")
            if london_type != "ANY":
                st.checkbox("Include NULL London codes", value=True, key="include_null_london", help="Default ON")
            preny_type = st.selectbox("Pre-NY type code", preny_codes, key="preny_type")
            if preny_type != "ANY":
                st.checkbox("Include NULL Pre-NY codes", value=True, key="include_null_preny", help="Default ON")

        with st.expander("Volatility filters", expanded=False):
            enable_atr = st.checkbox("Enable ATR filter", key="enable_atr")
            atr_range = None
            if enable_atr:
                if metadata.get("min_atr") is None or metadata.get("max_atr") is None:
                    st.info("ATR range not available.")
                else:
                    atr_range = st.slider(
                        "ATR 20 range",
                        float(metadata["min_atr"]),
                        float(metadata["max_atr"]),
                        step=1.0,
                        key="atr_range",
                    )

            enable_asia_range = st.checkbox("Enable Asia range filter", key="enable_asia_range")
            asia_range_values = None
            if enable_asia_range:
                if metadata.get("min_asia_range") is None or metadata.get("max_asia_range") is None:
                    st.info("Asia range bounds not available.")
                else:
                    asia_range_values = st.slider(
                        "Asia range",
                        float(metadata["min_asia_range"]),
                        float(metadata["max_asia_range"]),
                        step=1.0,
                        key="asia_range_values",
                    )

        with st.expander("Advanced", expanded=False):
            st.caption("Use Compare Mode to pin current filters as Query A or Query B.")
            st.checkbox("Top N days by R (descending)", key="top_n_enabled")
            if st.session_state["top_n_enabled"]:
                st.slider("Top N", min_value=10, max_value=500, key="top_n_value")

        st.markdown("---")
        if search_mode == "Simple":
            strategy = _render_simple_strategy_controls()
        else:
            strategy = _render_advanced_strategy_controls()

    filters = qe.Filters(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        orb_times=tuple(orb_times) if orb_times else tuple(qe.ORB_TIMES),
        break_dir=break_dir,
        outcomes=tuple(outcomes) if outcomes else tuple(qe.OUTCOME_OPTIONS),
        asia_type_code=None if asia_type == "ANY" else asia_type,
        include_null_asia=st.session_state.get("include_null_asia", True),
        london_type_code=None if london_type == "ANY" else london_type,
        include_null_london=st.session_state.get("include_null_london", True),
        pre_ny_type_code=None if preny_type == "ANY" else preny_type,
        include_null_pre_ny=st.session_state.get("include_null_preny", True),
        enable_atr_filter=enable_atr and atr_range is not None,
        atr_min=atr_range[0] if atr_range else None,
        atr_max=atr_range[1] if atr_range else None,
        enable_asia_range_filter=enable_asia_range and asia_range_values is not None,
        asia_range_min=asia_range_values[0] if asia_range_values else None,
        asia_range_max=asia_range_values[1] if asia_range_values else None,
    )
    return filters, strategy


def _render_simple_strategy_controls() -> qe.StrategyConfig:
    st.subheader("Simple Strategy")
    level_basis_label = st.selectbox(
        "Level basis",
        ["ORB boundary (High/Low)", "Half ORB (50% level)"],
        key="simple_level_basis",
        help="Half ORB uses the midpoint of the ORB range.",
    )
    entry_option = st.selectbox(
        "Entry confirmation",
        [
            "First 1m close beyond level",
            "2 x 1m closes beyond level",
            "3 x 1m closes beyond level",
            "First 5m close beyond level",
        ],
        key="simple_entry_option",
    )
    retest_required = st.checkbox("Require retest", key="simple_retest")
    retest_rule = "touch"
    pierce_ticks: Optional[int] = None
    rejection_tf = "1m"
    if retest_required:
        retest_type = st.selectbox("Retest type", ["Touch level", "Pierce then reclaim"], key="simple_retest_type")
        retest_rule = "pierce_by_ticks" if retest_type == "Pierce then reclaim" else "touch"
        if retest_rule == "pierce_by_ticks":
            pierce_ticks = st.number_input(
                "Pierce ticks",
                min_value=0,
                step=1,
                key="simple_pierce_ticks",
            )
        rejection_choice = st.selectbox(
            "Rejection confirmation",
            ["1m rejection close in breakout direction", "5m rejection close in breakout direction"],
            key="simple_rejection",
        )
        rejection_tf = "5m" if "5m" in rejection_choice else "1m"

    entry_model = "1m_close_break"
    confirm_closes = 1
    if entry_option == "2 x 1m closes beyond level":
        entry_model = "1m_close_break_confirmed"
        confirm_closes = 2
    elif entry_option == "3 x 1m closes beyond level":
        entry_model = "1m_close_break_confirmed"
        confirm_closes = 3
    elif entry_option == "First 5m close beyond level":
        entry_model = "5m_close_break"
        confirm_closes = 1
    if retest_required:
        entry_model = "break_retest_reject"

    max_stop_ticks = _parse_optional_int(st.text_input("Max stop size (ticks)", key="simple_max_stop"))
    cutoff_minutes = _parse_optional_int(
        st.text_input("Cutoff minutes after ORB end (0 = no cutoff)", key="simple_cutoff")
    )
    one_trade_per_orb = st.checkbox("One trade per ORB", key="simple_one_trade")

    level_basis = "orb_half" if "Half" in level_basis_label else "orb_boundary"
    return qe.StrategyConfig(
        level_basis=level_basis,
        entry_model=entry_model,
        confirm_closes=confirm_closes,
        retest_required=retest_required,
        retest_rule=retest_rule,
        pierce_ticks=pierce_ticks,
        rejection_tf=rejection_tf,
        stop_rule="ORB_opposite_boundary",
        max_stop_ticks=max_stop_ticks,
        cutoff_minutes=cutoff_minutes,
        one_trade_per_orb=one_trade_per_orb,
    )


def _render_advanced_strategy_controls() -> qe.StrategyConfig:
    st.subheader("Strategy Builder")
    preset_name = st.selectbox("Presets", list(qe.PRESETS.keys()), key="adv_preset")
    if st.button("Apply preset"):
        preset = qe.PRESETS[preset_name]
        st.session_state["adv_level_basis"] = preset.level_basis
        st.session_state["adv_entry_model"] = preset.entry_model
        st.session_state["adv_confirm_closes"] = preset.confirm_closes
        st.session_state["adv_retest_required"] = preset.retest_required
        st.session_state["adv_retest_rule"] = preset.retest_rule
        st.session_state["adv_pierce_ticks"] = preset.pierce_ticks or 0
        st.session_state["adv_rejection_tf"] = preset.rejection_tf
        st.session_state["adv_max_stop"] = "" if preset.max_stop_ticks is None else str(preset.max_stop_ticks)
        st.session_state["adv_cutoff"] = "" if preset.cutoff_minutes is None else str(preset.cutoff_minutes)
        st.session_state["adv_one_trade"] = preset.one_trade_per_orb
        st.experimental_rerun()

    level_basis = st.selectbox(
        "Level basis",
        ["orb_boundary", "orb_half"],
        index=["orb_boundary", "orb_half"].index(st.session_state["adv_level_basis"]),
        key="adv_level_basis",
    )
    entry_model = st.selectbox(
        "Entry model",
        ["1m_close_break", "1m_close_break_confirmed", "5m_close_break", "break_retest_reject"],
        index=["1m_close_break", "1m_close_break_confirmed", "5m_close_break", "break_retest_reject"].index(
            st.session_state["adv_entry_model"]
        ),
        key="adv_entry_model",
    )
    confirm_closes = st.session_state.get("adv_confirm_closes", 1)
    if entry_model == "1m_close_break_confirmed":
        confirm_closes = st.slider("Confirm closes (1-3)", min_value=1, max_value=3, key="adv_confirm_closes")
    else:
        confirm_closes = 1

    retest_required = st.checkbox("Retest required", key="adv_retest_required")
    retest_rule = st.session_state.get("adv_retest_rule", "touch")
    pierce_ticks: Optional[int] = None
    if retest_required:
        retest_rule = st.selectbox(
            "Retest rule",
            ["touch", "pierce_by_ticks"],
            index=["touch", "pierce_by_ticks"].index(st.session_state["adv_retest_rule"]),
            key="adv_retest_rule",
        )
        if retest_rule == "pierce_by_ticks":
            pierce_ticks = st.number_input(
                "Pierce ticks",
                min_value=0,
                step=1,
                key="adv_pierce_ticks",
            )
    rejection_tf = st.session_state.get("adv_rejection_tf", "1m")
    if retest_required:
        rejection_tf = st.selectbox(
            "Rejection timeframe",
            ["1m", "5m"],
            index=["1m", "5m"].index(st.session_state["adv_rejection_tf"]),
            key="adv_rejection_tf",
        )
    max_stop_ticks = _parse_optional_int(st.text_input("Max stop size (ticks)", key="adv_max_stop"))
    cutoff_minutes = _parse_optional_int(st.text_input("Cutoff minutes after ORB end", key="adv_cutoff"))
    one_trade_per_orb = st.checkbox("One trade per ORB", key="adv_one_trade")

    return qe.StrategyConfig(
        level_basis=level_basis,
        entry_model=entry_model,
        confirm_closes=confirm_closes,
        retest_required=retest_required,
        retest_rule=retest_rule,
        pierce_ticks=pierce_ticks,
        rejection_tf=rejection_tf,
        stop_rule="ORB_opposite_boundary",
        max_stop_ticks=max_stop_ticks,
        cutoff_minutes=cutoff_minutes,
        one_trade_per_orb=one_trade_per_orb,
    )


def render_strategy_summary(strategy: qe.StrategyConfig, stats: Dict[str, Any], filters: qe.Filters):
    sentence_parts = [
        f"Levels: {'Half ORB' if strategy.level_basis == 'orb_half' else 'ORB boundary'}",
        f"Entry: {strategy.entry_model} ({strategy.confirm_closes} close{'s' if strategy.confirm_closes != 1 else ''})",
    ]
    if strategy.retest_required:
        sentence_parts.append(f"Retest: {strategy.retest_rule}")
        sentence_parts.append(f"Reject: {strategy.rejection_tf}")
    sentence_parts.append(f"Stop: opposite ORB boundary")
    if strategy.max_stop_ticks is not None:
        sentence_parts.append(f"Max stop: {strategy.max_stop_ticks}t")
    if strategy.cutoff_minutes is not None:
        sentence_parts.append(f"Cutoff: {strategy.cutoff_minutes}m")
    summary = " | ".join(sentence_parts)
    st.markdown(f"**Strategy Summary:** {summary}")

    badges = [
        f"ORB: {', '.join(filters.orb_times) if filters.orb_times else 'All'}",
        f"Direction: {filters.break_dir}",
        f"Level: {'Half' if strategy.level_basis == 'orb_half' else 'Boundary'}",
        f"Trades: {stats['trades']}",
    ]
    st.caption(" | ".join(badges))


def render_stats(filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig):
    stats = load_headline_stats(filters_key, strategy_key, filters, strategy)
    trades = stats["trades"]
    wins = stats["wins"]
    win_rate = (wins / trades) * 100 if trades else 0.0
    avg_r = stats["avg_r"] or 0.0
    total_r = stats["total_r"] or 0.0
    opportunities = stats["opportunities"]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Trades (WIN/LOSS)", f"{trades}")
    col2.metric("Win rate", f"{win_rate:.1f}%")
    col3.metric("Avg R", f"{avg_r:.2f}")
    col4.metric("Total R", f"{total_r:.2f}")
    col5.metric("Opportunities (all outcomes)", f"{opportunities}")

    st.caption(
        f"Baseline (date window only): {stats['base_trades']} trades / {stats['base_opportunities']} opportunities."
    )


def _equity_plot(df: pd.DataFrame, title: str):
    st.caption(title)
    if df.empty:
        st.info("No trades for the selected filters.")
        return
    fig, ax = plt.subplots()
    plot_df = df.dropna(subset=["date_local", "equity"])
    ax.plot(plot_df["date_local"], plot_df["equity"], color="#1f77b4")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative R")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    final_val = plot_df["equity"].iloc[-1]
    ax.annotate(
        f"Total R: {final_val:.2f}",
        xy=(plot_df["date_local"].iloc[-1], final_val),
        xytext=(0, 10),
        textcoords="offset points",
        ha="right",
        color="#1f77b4",
        fontsize=9,
    )
    st.pyplot(fig, clear_figure=True)


def render_charts(
    filters_key: Tuple[Any, ...],
    strategy_key: Tuple[Any, ...],
    filters: qe.Filters,
    strategy: qe.StrategyConfig,
    stats: Dict[str, Any],
):
    st.subheader("Charts")
    st.caption(
        f"ORB: {', '.join(filters.orb_times) if filters.orb_times else 'All'} | "
        f"Direction: {filters.break_dir} | "
        f"Level: {'Half' if strategy.level_basis == 'orb_half' else 'Boundary'} | "
        f"Trades: {stats.get('trades', 0)}"
    )
    eq_df = load_equity_curve(filters_key, strategy_key, filters, strategy)
    hist_df = load_histogram(filters_key, strategy_key, filters, strategy)

    c1, c2 = st.columns(2)

    with c1:
        _equity_plot(eq_df, "Equity curve (WIN/LOSS only, ordered by date and ORB)")

    with c2:
        st.caption("R-multiple distribution (WIN/LOSS)")
        if hist_df.empty:
            st.info("No trades to plot.")
        else:
            clean = hist_df.dropna()
            mean_r = clean["r_multiple"].mean()
            median_r = clean["r_multiple"].median()
            fig, ax = plt.subplots()
            ax.hist(clean["r_multiple"], bins=30, color="#ff7f0e", edgecolor="black", alpha=0.8)
            ax.axvline(mean_r, color="blue", linestyle="--", linewidth=1.5, label=f"Mean {mean_r:.2f}")
            ax.axvline(median_r, color="green", linestyle=":", linewidth=1.5, label=f"Median {median_r:.2f}")
            ax.set_xlabel("R multiple")
            ax.set_ylabel("Count")
            ax.grid(True, alpha=0.3)
            ax.legend()
            st.pyplot(fig, clear_figure=True)


def render_heatmap(filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig):
    st.subheader("Session Heatmap (Asia x London)")
    heat_df = load_heatmap(filters_key, strategy_key, filters, strategy)
    if heat_df.empty:
        st.info("No data for current filters.")
        return

    metric = st.selectbox("Heatmap metric", ["Avg R", "Win Rate", "Count"], index=0)
    display_table = pd.DataFrame()
    if metric == "Avg R":
        table = heat_df.pivot(index="asia_type_code", columns="london_type_code", values="avg_r")
        display_table = table.round(3)
    elif metric == "Win Rate":
        table = heat_df.pivot(index="asia_type_code", columns="london_type_code", values="win_rate") * 100
        display_table = table.round(1)
    else:
        table = heat_df.pivot(index="asia_type_code", columns="london_type_code", values="count_rows")
        display_table = table.fillna(0).astype(int)

    st.dataframe(_sanitize_for_display(display_table).style.background_gradient(cmap="RdYlGn"), use_container_width=True)


def render_drilldown(filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig):
    st.subheader("Drilldown (max 500 rows)")
    order = "r_multiple_desc" if st.session_state.get("top_n_enabled", False) else "chronological"
    limit = min(500, st.session_state.get("top_n_value", 100)) if st.session_state.get("top_n_enabled", False) else 500

    df_display = load_drilldown(filters_key, strategy_key, filters, strategy, limit=limit, order=order)
    if df_display.empty:
        st.info("No rows for current filters.")
        return

    preferred_cols = [
        "date_local",
        "orb_time",
        "break_dir",
        "broke_side",
        "outcome",
        "r_multiple",
        "level_basis",
        "level_price",
        "orb_high",
        "orb_low",
        "orb_size",
        "confirm_closes_hit",
        "confirm_required",
        "retest_hit",
        "rejection_hit",
        "stop_ticks",
        "filtered_out_reason",
        "asia_type_code",
        "london_type_code",
        "pre_ny_type_code",
        "atr_20",
        "asia_range",
    ]
    cols = [c for c in preferred_cols if c in df_display.columns]
    if cols:
        df_display = df_display[cols]

    st.dataframe(_sanitize_for_display(df_display), use_container_width=True, hide_index=True)

    full_df = load_drilldown_full(filters_key, strategy_key, filters, strategy)
    csv_buf = io.StringIO()
    full_df.to_csv(csv_buf, index=False)
    st.download_button(
        label=f"Download CSV (full set: {len(full_df)} rows)",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name="orb_drilldown_full.csv",
        mime="text/csv",
    )


def render_funnel(filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig):
    st.subheader("Entry Path Funnel")
    counts = load_funnel(filters_key, strategy_key, filters, strategy)
    labels = [
        ("ORBs total", counts["total_orbs"]),
        ("Break occurred", counts["break_occurred"]),
        ("Confirm met", counts["confirm_met"]),
        ("Retest met", counts["retest_met"]),
        ("Rejection met", counts["rejection_met"]),
        ("Trades taken", counts["trades"]),
        ("Wins", counts["wins"]),
        ("Losses", counts["losses"]),
    ]
    cols = st.columns(len(labels))
    for col, (label, val) in zip(cols, labels):
        col.metric(label, val)


def render_compare_mode(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...], filters: qe.Filters, strategy: qe.StrategyConfig
):
    if "saved_filters" not in st.session_state:
        st.session_state["saved_filters"] = {"A": None, "B": None}

    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("Save as Query A"):
        st.session_state["saved_filters"]["A"] = {
            "filters": qe.serialize_filters(filters),
            "strategy": qe.serialize_strategy(strategy),
        }
    if col_b.button("Save as Query B"):
        st.session_state["saved_filters"]["B"] = {
            "filters": qe.serialize_filters(filters),
            "strategy": qe.serialize_strategy(strategy),
        }

    saved_a = st.session_state["saved_filters"].get("A")
    saved_b = st.session_state["saved_filters"].get("B")
    if not saved_a and not saved_b:
        return

    st.subheader("Compare Mode")
    c1, c2 = st.columns(2)

    if saved_a:
        filters_a = qe.filters_from_dict(saved_a["filters"])
        strategy_a = qe.strategy_from_dict(saved_a["strategy"])
        fk_a = qe.filters_key(filters_a)
        sk_a = qe.strategy_key(strategy_a)
        stats_a = load_headline_stats(fk_a, sk_a, filters_a, strategy_a)
        with c1:
            st.markdown("**Query A**")
            st.metric("Trades", stats_a["trades"])
            st.metric("Win rate", f"{(stats_a['wins']/stats_a['trades']*100) if stats_a['trades'] else 0:.1f}%")
            st.metric("Avg R", f"{(stats_a['avg_r'] or 0):.2f}")
            st.metric("Total R", f"{(stats_a['total_r'] or 0):.2f}")
            _equity_plot(load_equity_curve(fk_a, sk_a, filters_a, strategy_a), "Equity (Query A)")

    if saved_b:
        filters_b = qe.filters_from_dict(saved_b["filters"])
        strategy_b = qe.strategy_from_dict(saved_b["strategy"])
        fk_b = qe.filters_key(filters_b)
        sk_b = qe.strategy_key(strategy_b)
        stats_b = load_headline_stats(fk_b, sk_b, filters_b, strategy_b)
        with c2:
            st.markdown("**Query B**")
            st.metric("Trades", stats_b["trades"])
            st.metric("Win rate", f"{(stats_b['wins']/stats_b['trades']*100) if stats_b['trades'] else 0:.1f}%")
            st.metric("Avg R", f"{(stats_b['avg_r'] or 0):.2f}")
            st.metric("Total R", f"{(stats_b['total_r'] or 0):.2f}")
            _equity_plot(load_equity_curve(fk_b, sk_b, filters_b, strategy_b), "Equity (Query B)")


def main():
    st.title("Dashboard A — ORB Edge Research")
    st.caption("Filters apply instantly using v_orb_trades (no data duplication).")

    metadata = load_metadata()
    _set_defaults(metadata)
    filters, strategy = build_filters_and_strategy(metadata)
    if filters is None:
        return

    filters_key = qe.filters_key(filters)
    strategy_key = qe.strategy_key(strategy)

    stats = load_headline_stats(filters_key, strategy_key, filters, strategy)
    render_strategy_summary(strategy, stats, filters)
    render_stats(filters_key, strategy_key, filters, strategy)
    render_funnel(filters_key, strategy_key, filters, strategy)
    render_compare_mode(filters_key, strategy_key, filters, strategy)
    render_charts(filters_key, strategy_key, filters, strategy, stats)
    render_heatmap(filters_key, strategy_key, filters, strategy)
    render_drilldown(filters_key, strategy_key, filters, strategy)


if __name__ == "__main__":
    main()
