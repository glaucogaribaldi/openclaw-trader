import itertools
import json
from pathlib import Path

import pandas as pd
import numpy as np

# ==========================================
# 策略名称：亢龙有悔 (Dragon's Regret v1.1)
# 审计状态：逻辑完备 / 实战未验证
# ==========================================


class SpringReversionStrategy:
    def __init__(self):
        self.CONFIG = {
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "risk_per_trade_pct": 0.01,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "rsi_period": 14,
            "rsi_ob": 80,
            "rsi_os": 20,
            "vol_ma_period": 20,
            "return_zscore_period": 20,
            "body_atr_threshold": 1.8,
            "return_zscore_threshold": 2.0,
            "trend_filter_enabled": True,
            "higher_tf_multiple": 4,
            "higher_tf_ma_period": 20,
            "higher_tf_slope_period": 3,
            "higher_tf_slope_atr_threshold": 1.0,
            "vol_spike_multiplier": 2.5,
            "max_hold_time": 120,
            "trailing_callback": 0.005,
            "entry_order_type": "taker",
            "exit_order_type": "taker",
            "maker_fee_rate": 0.0002,
            "taker_fee_rate": 0.0007,
            "maker_slippage_bps": 0.0,
            "taker_slippage_bps": 1.0,
        }
        self.initial_account_balance = 1000.0
        self.reset_state()

    def reset_state(self, starting_balance=None):
        if starting_balance is not None:
            self.initial_account_balance = float(starting_balance)

        self.current_position = None
        self.account_balance = float(self.initial_account_balance)
        self.trade_log = []

    def get_min_required_bars(self):
        higher_tf_required_bars = self.CONFIG["higher_tf_multiple"] * (
            self.CONFIG["higher_tf_ma_period"] + self.CONFIG["higher_tf_slope_period"] + 1
        )
        return (
            max(
                self.CONFIG["atr_period"],
                self.CONFIG["rsi_period"],
                self.CONFIG["vol_ma_period"],
                self.CONFIG["return_zscore_period"],
                higher_tf_required_bars,
            )
            + 2
        )

    def get_timeframe_seconds(self):
        timeframe = str(self.CONFIG["timeframe"]).strip().lower()
        if timeframe.endswith("m"):
            return int(timeframe[:-1]) * 60
        if timeframe.endswith("h"):
            return int(timeframe[:-1]) * 3600
        if timeframe.endswith("d"):
            return int(timeframe[:-1]) * 86400
        raise ValueError(f"Unsupported timeframe: {self.CONFIG['timeframe']}")

    def prepare_market_data(self, market_data):
        df = pd.DataFrame(market_data).copy()
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        missing_columns = sorted(required_columns.difference(df.columns))
        if missing_columns:
            raise ValueError(f"market_data 缺少字段: {', '.join(missing_columns)}")

        numeric_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=numeric_columns)
        if df.empty:
            raise ValueError("market_data 没有可用K线")

        return df.sort_values("timestamp").reset_index(drop=True)

    def calculate_indicators(self, df):
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.CONFIG["atr_period"]).mean()

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.CONFIG["rsi_period"]).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.CONFIG["rsi_period"]).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        df["vol_ma"] = df["volume"].rolling(window=self.CONFIG["vol_ma_period"]).mean()
        df["roc"] = df["close"].pct_change()
        df["body_change"] = df["close"] - df["open"]
        df["body_atr_ratio"] = df["body_change"] / df["atr"].replace(0, np.nan)
        df["roc_mean"] = df["roc"].rolling(
            window=self.CONFIG["return_zscore_period"]
        ).mean()
        df["roc_std"] = df["roc"].rolling(
            window=self.CONFIG["return_zscore_period"]
        ).std(ddof=0)
        df["return_zscore"] = (
            (df["roc"] - df["roc_mean"]) / df["roc_std"].replace(0, np.nan)
        )
        higher_tf_seconds = self.get_timeframe_seconds() * self.CONFIG["higher_tf_multiple"]
        df["higher_tf_bucket"] = (df["timestamp"] // higher_tf_seconds).astype(int)

        higher_tf_df = (
            df.groupby("higher_tf_bucket", sort=True)
            .agg(higher_tf_close=("close", "last"))
            .reset_index()
        )
        higher_tf_df["higher_tf_ema"] = higher_tf_df["higher_tf_close"].ewm(
            span=self.CONFIG["higher_tf_ma_period"],
            adjust=False,
        ).mean()
        higher_tf_df["higher_tf_slope"] = (
            higher_tf_df["higher_tf_ema"]
            - higher_tf_df["higher_tf_ema"].shift(self.CONFIG["higher_tf_slope_period"])
        )
        higher_tf_df["higher_tf_ema"] = higher_tf_df["higher_tf_ema"].shift(1)
        higher_tf_df["higher_tf_close"] = higher_tf_df["higher_tf_close"].shift(1)
        higher_tf_df["higher_tf_slope"] = higher_tf_df["higher_tf_slope"].shift(1)

        df = df.merge(higher_tf_df, on="higher_tf_bucket", how="left")
        df["higher_tf_slope_atr_ratio"] = (
            df["higher_tf_slope"] / df["atr"].replace(0, np.nan)
        )
        df["higher_tf_distance_atr"] = (
            (df["close"] - df["higher_tf_ema"]) / df["atr"].replace(0, np.nan)
        )
        df["trend_regime"] = np.select(
            [
                df["higher_tf_slope_atr_ratio"]
                >= self.CONFIG["higher_tf_slope_atr_threshold"],
                df["higher_tf_slope_atr_ratio"]
                <= -self.CONFIG["higher_tf_slope_atr_threshold"],
            ],
            ["uptrend", "downtrend"],
            default="sideways",
        )

        return df

    def check_entry_signal(self, df, end_idx=None):
        if end_idx is None:
            end_idx = len(df) - 1
        if end_idx + 1 < self.get_min_required_bars():
            return None

        last_row = df.iloc[end_idx]
        prev_row = df.iloc[end_idx - 1]
        indicator_columns = [
            "atr",
            "rsi",
            "vol_ma",
            "roc",
            "body_atr_ratio",
            "return_zscore",
            "higher_tf_ema",
            "higher_tf_slope_atr_ratio",
        ]
        if df[indicator_columns].iloc[end_idx - 1 : end_idx + 1].isna().any().any():
            return None

        overextended_short = (
            last_row["body_atr_ratio"] >= self.CONFIG["body_atr_threshold"]
            and last_row["return_zscore"] >= self.CONFIG["return_zscore_threshold"]
            and last_row["rsi"] >= self.CONFIG["rsi_ob"]
        )
        overextended_long = (
            last_row["body_atr_ratio"] <= -self.CONFIG["body_atr_threshold"]
            and last_row["return_zscore"] <= -self.CONFIG["return_zscore_threshold"]
            and last_row["rsi"] <= self.CONFIG["rsi_os"]
        )
        if not overextended_short and not overextended_long:
            return None

        volume_climax = last_row["volume"] > (
            last_row["vol_ma"] * self.CONFIG["vol_spike_multiplier"]
        )
        momentum_deceleration = (
            abs(last_row["roc"]) < abs(prev_row["roc"])
            and abs(last_row["body_atr_ratio"]) <= abs(prev_row["body_atr_ratio"])
        )

        if volume_climax and momentum_deceleration:
            if self.CONFIG["trend_filter_enabled"]:
                trend_regime = str(last_row["trend_regime"])
                if overextended_short and trend_regime == "uptrend":
                    return None
                if overextended_long and trend_regime == "downtrend":
                    return None
            if overextended_short:
                return "SHORT"
            if overextended_long:
                return "BUY"

        return None

    def calculate_position_size(self, entry_price, atr_val):
        if pd.isna(entry_price) or pd.isna(atr_val) or entry_price <= 0 or atr_val <= 0:
            return 0, 0

        stop_distance = atr_val * self.CONFIG["atr_multiplier"]
        if stop_distance == 0:
            return 0, 0

        risk_amount = self.account_balance * self.CONFIG["risk_per_trade_pct"]
        quantity = risk_amount / stop_distance
        return quantity, stop_distance

    def get_fee_rate(self, order_type):
        normalized_order_type = str(order_type).strip().lower()
        if normalized_order_type == "maker":
            return float(self.CONFIG["maker_fee_rate"])
        if normalized_order_type == "taker":
            return float(self.CONFIG["taker_fee_rate"])
        raise ValueError(f"Unsupported order_type: {order_type}")

    def get_slippage_rate(self, order_type):
        normalized_order_type = str(order_type).strip().lower()
        if normalized_order_type == "maker":
            return float(self.CONFIG["maker_slippage_bps"]) / 10000.0
        if normalized_order_type == "taker":
            return float(self.CONFIG["taker_slippage_bps"]) / 10000.0
        raise ValueError(f"Unsupported order_type: {order_type}")

    def apply_execution_model(self, raw_price, quantity, order_side, order_type):
        price = float(raw_price)
        qty = float(quantity)
        if price <= 0 or qty <= 0:
            raise ValueError("Execution model requires positive price and quantity")

        normalized_side = str(order_side).strip().upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError(f"Unsupported order_side: {order_side}")

        slip_multiplier = 1.0 if normalized_side == "BUY" else -1.0
        slippage_rate = self.get_slippage_rate(order_type)
        fill_price = price * (1 + slip_multiplier * slippage_rate)
        notional = fill_price * qty
        fee = notional * self.get_fee_rate(order_type)
        return {
            "raw_price": price,
            "fill_price": fill_price,
            "quantity": qty,
            "notional": notional,
            "fee": fee,
            "slippage_cost": abs(fill_price - price) * qty,
            "order_side": normalized_side,
            "order_type": str(order_type).strip().lower(),
        }

    def open_position(self, signal, current_row):
        qty, dist = self.calculate_position_size(current_row["close"], current_row["atr"])
        if qty <= 0 or dist <= 0:
            self.log_event("跳过开仓: 仓位或止损距离无效")
            return None

        entry_order_side = "BUY" if signal == "BUY" else "SELL"
        entry_execution = self.apply_execution_model(
            raw_price=current_row["close"],
            quantity=qty,
            order_side=entry_order_side,
            order_type=self.CONFIG["entry_order_type"],
        )
        entry_price = float(entry_execution["fill_price"])
        entry_fee = float(entry_execution["fee"])
        self.current_position = {
            "side": signal,
            "entry_price": entry_price,
            "qty": qty,
            "stop_loss": entry_price - dist if signal == "BUY" else entry_price + dist,
            "entry_time": current_row["timestamp"],
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "entry_fee": entry_fee,
            "entry_atr": float(current_row["atr"]),
            "entry_raw_price": float(current_row["close"]),
            "entry_order_type": entry_execution["order_type"],
            "entry_order_side": entry_execution["order_side"],
            "entry_slippage_cost": float(entry_execution["slippage_cost"]),
        }
        self.log_event(
            f"开仓 {signal}: 成交价 {entry_price:.4f}, 原始价 {float(current_row['close']):.4f}, "
            f"止损距离 {dist:.4f}, 入场费 {entry_fee:.4f}"
        )
        return self.current_position

    def estimate_exit_metrics(self, price):
        if self.current_position is None:
            return {
                "exit_fill_price": float(price),
                "exit_fee": 0.0,
                "gross_pnl": 0.0,
                "net_open_pnl": 0.0,
                "slippage_cost": 0.0,
            }

        pos = self.current_position
        entry_price = float(pos["entry_price"])
        quantity = float(pos["qty"])
        exit_order_side = "SELL" if pos["side"] == "BUY" else "BUY"
        exit_execution = self.apply_execution_model(
            raw_price=price,
            quantity=quantity,
            order_side=exit_order_side,
            order_type=self.CONFIG["exit_order_type"],
        )
        exit_fill_price = float(exit_execution["fill_price"])
        if pos["side"] == "BUY":
            gross_pnl = (exit_fill_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_fill_price) * quantity

        entry_fee = float(pos.get("entry_fee", 0.0))
        exit_fee = float(exit_execution["fee"])
        return {
            "exit_fill_price": exit_fill_price,
            "exit_fee": exit_fee,
            "gross_pnl": gross_pnl,
            "net_open_pnl": gross_pnl - entry_fee - exit_fee,
            "slippage_cost": float(exit_execution["slippage_cost"]),
            "exit_order_type": exit_execution["order_type"],
            "exit_order_side": exit_execution["order_side"],
        }

    def calculate_unrealized_pnl(self, price):
        return float(self.estimate_exit_metrics(price)["net_open_pnl"])

    def calculate_mark_to_market_equity(self, price):
        if self.current_position is None:
            return float(self.account_balance)

        return float(self.account_balance + self.calculate_unrealized_pnl(price))

    def build_equity_point(self, current_row):
        price = float(current_row["close"])
        exit_metrics = self.estimate_exit_metrics(price)
        unrealized_pnl = float(exit_metrics["net_open_pnl"])
        return {
            "timestamp": int(current_row["timestamp"]),
            "close": price,
            "balance": float(self.account_balance),
            "equity": self.calculate_mark_to_market_equity(price),
            "unrealized_pnl": unrealized_pnl,
            "gross_open_pnl": float(exit_metrics["gross_pnl"]),
            "estimated_exit_price": float(exit_metrics["exit_fill_price"]),
            "estimated_exit_fee": float(exit_metrics["exit_fee"]),
            "in_position": self.current_position is not None,
            "position_side": None
            if self.current_position is None
            else self.current_position["side"],
        }

    def annotate_equity_curve(self, equity_curve):
        if not equity_curve:
            return equity_curve

        peak_equity = float("-inf")
        for point in equity_curve:
            equity = float(point["equity"])
            peak_equity = max(peak_equity, equity)
            drawdown = peak_equity - equity
            drawdown_pct = 0.0 if peak_equity <= 0 else drawdown / peak_equity
            point["peak_equity"] = peak_equity
            point["drawdown"] = drawdown
            point["drawdown_pct"] = drawdown_pct
        return equity_curve

    def summarize_backtest(self, equity_curve, bars_processed):
        wins = sum(1 for trade in self.trade_log if trade["net_pnl"] > 0)
        losses = sum(1 for trade in self.trade_log if trade["net_pnl"] < 0)
        gross_profit = sum(
            trade["net_pnl"] for trade in self.trade_log if trade["net_pnl"] > 0
        )
        gross_loss = sum(
            -trade["net_pnl"] for trade in self.trade_log if trade["net_pnl"] < 0
        )
        hold_minutes = [
            trade["hold_minutes"]
            for trade in self.trade_log
            if trade["hold_minutes"] is not None
        ]
        max_drawdown = max((point["drawdown"] for point in equity_curve), default=0.0)
        max_drawdown_pct = max(
            (point["drawdown_pct"] for point in equity_curve),
            default=0.0,
        )
        final_equity = (
            float(equity_curve[-1]["equity"])
            if equity_curve
            else float(self.account_balance)
        )
        return {
            "bars_processed": bars_processed,
            "warmup_bars": self.get_min_required_bars(),
            "starting_balance": float(self.initial_account_balance),
            "final_balance": float(self.account_balance),
            "final_equity": final_equity,
            "net_pnl": float(self.account_balance - self.initial_account_balance),
            "return_pct": 0.0
            if self.initial_account_balance == 0
            else float(
                (final_equity - self.initial_account_balance)
                / self.initial_account_balance
            ),
            "total_trades": len(self.trade_log),
            "wins": wins,
            "losses": losses,
            "win_rate": 0.0 if not self.trade_log else wins / len(self.trade_log),
            "avg_hold_minutes": 0.0 if not hold_minutes else float(np.mean(hold_minutes)),
            "profit_factor": None if gross_loss == 0 else gross_profit / gross_loss,
            "max_drawdown": float(max_drawdown),
            "max_drawdown_pct": float(max_drawdown_pct),
            "open_position": self.current_position is not None,
        }

    def run_backtest(
        self,
        market_data,
        starting_balance=None,
        close_open_position_on_finish=True,
        export_dir=None,
        export_prefix="spring_reversion",
    ):
        self.reset_state(starting_balance)
        df = self.prepare_market_data(market_data)
        df = self.calculate_indicators(df)
        equity_curve = []
        min_required_bars = self.get_min_required_bars()

        for idx in range(len(df)):
            current_row = df.iloc[idx]
            if idx + 1 >= min_required_bars:
                if self.current_position is None:
                    signal = self.check_entry_signal(df, end_idx=idx)
                    if signal:
                        self.open_position(signal, current_row)
                else:
                    self.monitor_exit_conditions(current_row)

            equity_curve.append(self.build_equity_point(current_row))

        if (
            close_open_position_on_finish
            and self.current_position is not None
            and not df.empty
        ):
            last_row = df.iloc[-1]
            self.close_position(
                float(last_row["close"]),
                "回测结束强制平仓",
                int(last_row["timestamp"]),
            )
            equity_curve[-1] = self.build_equity_point(last_row)

        equity_curve = self.annotate_equity_curve(equity_curve)
        result = {
            "summary": self.summarize_backtest(equity_curve, len(df)),
            "trades": list(self.trade_log),
            "equity_curve": equity_curve,
        }
        if export_dir:
            result["exports"] = self.export_backtest_results(
                result,
                output_dir=export_dir,
                file_prefix=export_prefix,
            )
        return result

    def export_backtest_results(self, backtest_result, output_dir, file_prefix="spring_reversion"):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        summary_path = output_path / f"{file_prefix}_summary.json"
        trades_path = output_path / f"{file_prefix}_trades.csv"
        equity_curve_path = output_path / f"{file_prefix}_equity_curve.csv"

        with summary_path.open("w", encoding="utf-8") as file_obj:
            json.dump(backtest_result["summary"], file_obj, ensure_ascii=False, indent=2)

        pd.DataFrame(backtest_result["trades"]).to_csv(trades_path, index=False)
        pd.DataFrame(backtest_result["equity_curve"]).to_csv(equity_curve_path, index=False)

        return {
            "summary": str(summary_path),
            "trades": str(trades_path),
            "equity_curve": str(equity_curve_path),
        }

    def build_parameter_combinations(self, parameter_grid):
        if isinstance(parameter_grid, list):
            return [dict(item) for item in parameter_grid]

        if not isinstance(parameter_grid, dict):
            raise ValueError("parameter_grid must be a dict of lists or a list of dicts")

        keys = list(parameter_grid.keys())
        value_matrix = []
        for key in keys:
            value = parameter_grid[key]
            if isinstance(value, (list, tuple)):
                if not value:
                    raise ValueError(f"parameter_grid[{key}] cannot be empty")
                value_matrix.append(list(value))
            else:
                value_matrix.append([value])

        return [
            dict(zip(keys, combo, strict=False))
            for combo in itertools.product(*value_matrix)
        ]

    def run_backtest_with_config(self, market_data, config_override=None, **kwargs):
        original_config = dict(self.CONFIG)
        try:
            if config_override:
                self.CONFIG.update(config_override)
            return self.run_backtest(market_data, **kwargs)
        finally:
            self.CONFIG = original_config

    def run_parameter_scan(
        self,
        market_data,
        parameter_grid,
        starting_balance=None,
        score_key="final_equity",
        maximize=True,
        close_open_position_on_finish=True,
    ):
        combinations = self.build_parameter_combinations(parameter_grid)
        results = []

        for config_override in combinations:
            backtest_result = self.run_backtest_with_config(
                market_data,
                config_override=config_override,
                starting_balance=starting_balance,
                close_open_position_on_finish=close_open_position_on_finish,
            )
            summary = backtest_result["summary"]
            score = summary.get(score_key)
            results.append(
                {
                    "config_override": dict(config_override),
                    "score": score,
                    "summary": summary,
                }
            )

        results.sort(
            key=lambda item: (
                item["score"] is None,
                -(item["score"]) if maximize and item["score"] is not None else item["score"],
            )
        )
        if not maximize:
            results.sort(
                key=lambda item: (
                    item["score"] is None,
                    item["score"] if item["score"] is not None else float("inf"),
                )
            )

        for index, result in enumerate(results, start=1):
            result["rank"] = index

        return {
            "results": results,
            "best": None if not results else results[0],
            "score_key": score_key,
            "maximize": maximize,
        }

    def run_walk_forward(
        self,
        market_data,
        parameter_grid,
        train_bars,
        test_bars,
        step_bars=None,
        starting_balance=None,
        score_key="final_equity",
        maximize=True,
        close_open_position_on_finish=True,
    ):
        if train_bars <= 0 or test_bars <= 0:
            raise ValueError("train_bars and test_bars must be > 0")

        prepared_df = self.prepare_market_data(market_data)
        if step_bars is None:
            step_bars = test_bars
        if step_bars <= 0:
            raise ValueError("step_bars must be > 0")

        current_balance = (
            float(self.initial_account_balance)
            if starting_balance is None
            else float(starting_balance)
        )
        starting_point_balance = current_balance
        segments = []
        combined_trades = []
        combined_equity_curve = []
        offset = 0

        while offset + train_bars + test_bars <= len(prepared_df):
            train_slice = prepared_df.iloc[offset : offset + train_bars].to_dict("records")
            test_slice = prepared_df.iloc[
                offset + train_bars : offset + train_bars + test_bars
            ].to_dict("records")
            scan_result = self.run_parameter_scan(
                train_slice,
                parameter_grid=parameter_grid,
                starting_balance=current_balance,
                score_key=score_key,
                maximize=maximize,
                close_open_position_on_finish=close_open_position_on_finish,
            )
            best_result = scan_result["best"]
            if best_result is None:
                break

            test_result = self.run_backtest_with_config(
                test_slice,
                config_override=best_result["config_override"],
                starting_balance=current_balance,
                close_open_position_on_finish=close_open_position_on_finish,
            )
            segment_index = len(segments) + 1
            segment_trades = []
            for trade in test_result["trades"]:
                trade_with_segment = dict(trade)
                trade_with_segment["segment"] = segment_index
                segment_trades.append(trade_with_segment)
            combined_trades.extend(segment_trades)
            combined_equity_curve.extend(
                dict(point, segment=segment_index) for point in test_result["equity_curve"]
            )

            segments.append(
                {
                    "segment": segment_index,
                    "train_start_ts": int(train_slice[0]["timestamp"]),
                    "train_end_ts": int(train_slice[-1]["timestamp"]),
                    "test_start_ts": int(test_slice[0]["timestamp"]),
                    "test_end_ts": int(test_slice[-1]["timestamp"]),
                    "selected_config": dict(best_result["config_override"]),
                    "train_score": best_result["score"],
                    "train_summary": best_result["summary"],
                    "test_summary": test_result["summary"],
                }
            )
            current_balance = float(test_result["summary"]["final_balance"])
            offset += step_bars

        combined_equity_curve = self.annotate_equity_curve(combined_equity_curve)
        final_equity = (
            current_balance if not combined_equity_curve else combined_equity_curve[-1]["equity"]
        )
        summary = {
            "segments": len(segments),
            "starting_balance": starting_point_balance,
            "final_balance": current_balance,
            "final_equity": float(final_equity),
            "net_pnl": float(current_balance - starting_point_balance),
            "return_pct": 0.0
            if starting_point_balance == 0
            else float((final_equity - starting_point_balance) / starting_point_balance),
            "total_trades": len(combined_trades),
            "max_drawdown": float(
                max((point["drawdown"] for point in combined_equity_curve), default=0.0)
            ),
            "max_drawdown_pct": float(
                max((point["drawdown_pct"] for point in combined_equity_curve), default=0.0)
            ),
            "score_key": score_key,
        }
        return {
            "summary": summary,
            "segments": segments,
            "trades": combined_trades,
            "equity_curve": combined_equity_curve,
        }

    def execute_trade_logic(self, market_data):
        try:
            df = self.prepare_market_data(market_data)
        except ValueError as exc:
            self.log_event(f"跳过执行: {exc}")
            return None

        df = self.calculate_indicators(df)
        if len(df) < self.get_min_required_bars():
            self.log_event(
                f"数据未预热完成: 当前 {len(df)} 根, 至少需要 {self.get_min_required_bars()} 根"
            )
            return None

        if self.current_position is None:
            signal = self.check_entry_signal(df)
            if signal:
                self.open_position(signal, df.iloc[-1])
        else:
            self.monitor_exit_conditions(df.iloc[-1])

        return self.current_position

    def monitor_exit_conditions(self, current_row):
        pos = self.current_position
        if pos is None:
            return

        price = current_row["close"]
        entry_price = pos["entry_price"]

        # ATR 硬止损
        if (pos["side"] == "BUY" and price <= pos["stop_loss"]) or (
            pos["side"] == "SHORT" and price >= pos["stop_loss"]
        ):
            self.close_position(price, "ATR硬止损", current_row["timestamp"])
            return

        # 追踪止盈
        if pos["side"] == "BUY":
            pos["highest_price"] = max(pos["highest_price"], price)
            retracement = (pos["highest_price"] - price) / pos["highest_price"]
            trailing_armed = pos["highest_price"] >= entry_price * (
                1 + self.CONFIG["trailing_callback"]
            )
            locked_profit = price > entry_price
        else:
            pos["lowest_price"] = min(pos["lowest_price"], price)
            retracement = (price - pos["lowest_price"]) / pos["lowest_price"]
            trailing_armed = pos["lowest_price"] <= entry_price * (
                1 - self.CONFIG["trailing_callback"]
            )
            locked_profit = price < entry_price

        if (
            trailing_armed
            and locked_profit
            and retracement >= self.CONFIG["trailing_callback"]
        ):
            self.close_position(price, "追踪止盈回撤", current_row["timestamp"])
            return

        # 时间止损
        if (current_row["timestamp"] - pos["entry_time"]) >= (
            self.CONFIG["max_hold_time"] * 60
        ):
            self.close_position(price, "回归动能耗尽(时间过滤)", current_row["timestamp"])

    def close_position(self, price, reason, exit_time=None):
        if self.current_position is None:
            self.log_event(f"忽略平仓: 当前无持仓, 原因 {reason}")
            return None

        pos = self.current_position
        side = pos["side"]
        entry_price = float(pos["entry_price"])
        quantity = float(pos["qty"])
        entry_fee = float(pos.get("entry_fee", 0.0))
        exit_order_side = "SELL" if side == "BUY" else "BUY"
        exit_execution = self.apply_execution_model(
            raw_price=price,
            quantity=quantity,
            order_side=exit_order_side,
            order_type=self.CONFIG["exit_order_type"],
        )
        exit_price = float(exit_execution["fill_price"])
        exit_fee = float(exit_execution["fee"])
        if side == "BUY":
            gross_pnl = (exit_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_price) * quantity
        fees = entry_fee + exit_fee
        net_pnl = gross_pnl - fees
        self.account_balance += net_pnl
        hold_minutes = (
            None if exit_time is None else (int(exit_time) - int(pos["entry_time"])) / 60.0
        )

        closed_trade = {
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": quantity,
            "gross_pnl": gross_pnl,
            "entry_raw_price": float(pos.get("entry_raw_price", entry_price)),
            "exit_raw_price": float(price),
            "entry_order_type": pos.get("entry_order_type"),
            "exit_order_type": exit_execution["order_type"],
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "entry_slippage_cost": float(pos.get("entry_slippage_cost", 0.0)),
            "exit_slippage_cost": float(exit_execution["slippage_cost"]),
            "fees": fees,
            "net_pnl": net_pnl,
            "account_balance": self.account_balance,
            "entry_time": pos["entry_time"],
            "exit_time": exit_time,
            "hold_minutes": hold_minutes,
            "reason": reason,
        }
        self.trade_log.append(closed_trade)
        self.current_position = None
        self.log_event(
            f"平仓: 价格 {price}, 净盈亏 {net_pnl:.4f}, 余额 {self.account_balance:.4f}, 原因 {reason}"
        )
        return closed_trade

    def log_event(self, msg):
        print(f"[STRATEGY_LOG] {msg}")
