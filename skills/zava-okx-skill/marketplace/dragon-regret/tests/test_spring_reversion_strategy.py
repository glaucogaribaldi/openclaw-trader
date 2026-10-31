#!/usr/bin/env python3
"""Tests for SpringReversionStrategy."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import pandas as pd
import tempfile
import unittest


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "spring_reversion_strategy.py"
    spec = importlib.util.spec_from_file_location("spring_reversion_strategy", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load spring_reversion_strategy module")
    spec.loader.exec_module(module)
    return module


class WarmupGuardTest(unittest.TestCase):
    def test_execute_trade_logic_short_input_does_not_raise(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        logs: list[str] = []
        strategy.log_event = lambda msg: logs.append(msg)

        market_data = [
            {
                "timestamp": 1,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            }
        ]

        result = strategy.execute_trade_logic(market_data)

        self.assertIsNone(result)
        self.assertIsNone(strategy.current_position)
        self.assertTrue(any("数据未预热完成" in msg for msg in logs))


class TrailingExitTest(unittest.TestCase):
    def test_trailing_exit_requires_locked_profit(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.CONFIG.update(
            {
                "maker_fee_rate": 0.0,
                "taker_fee_rate": 0.0,
                "maker_slippage_bps": 0.0,
                "taker_slippage_bps": 0.0,
            }
        )
        logs: list[str] = []
        strategy.log_event = lambda msg: logs.append(msg)
        strategy.current_position = {
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "stop_loss": 98.0,
            "entry_time": 0,
            "highest_price": 100.0,
            "lowest_price": 100.0,
        }

        strategy.monitor_exit_conditions({"close": 99.4, "timestamp": 60})

        self.assertIsNotNone(strategy.current_position)
        self.assertEqual(logs, [])


class NormalizedSignalTest(unittest.TestCase):
    def test_check_entry_signal_uses_atr_and_zscore_thresholds(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        min_bars = strategy.get_min_required_bars()
        rows = []

        for timestamp in range(min_bars):
            rows.append(
                {
                    "timestamp": timestamp,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 100.0,
                    "atr": 1.0,
                    "rsi": 50.0,
                    "vol_ma": 100.0,
                    "roc": 0.01,
                    "body_atr_ratio": 0.5,
                    "return_zscore": 0.5,
                    "higher_tf_ema": 100.0,
                    "higher_tf_slope_atr_ratio": 0.0,
                    "trend_regime": "sideways",
                }
            )

        rows[-2].update(
            {
                "open": 100.0,
                "close": 102.6,
                "volume": 300.0,
                "rsi": 84.0,
                "roc": 0.04,
                "body_atr_ratio": 2.5,
                "return_zscore": 3.0,
            }
        )
        rows[-1].update(
            {
                "open": 100.0,
                "close": 102.0,
                "volume": 280.0,
                "rsi": 82.0,
                "roc": 0.02,
                "body_atr_ratio": 2.1,
                "return_zscore": 2.4,
            }
        )

        signal = strategy.check_entry_signal(pd.DataFrame(rows))

        self.assertEqual(signal, "SHORT")

    def test_higher_timeframe_uptrend_blocks_counter_trend_short(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        min_bars = strategy.get_min_required_bars()
        rows = []

        for timestamp in range(min_bars):
            rows.append(
                {
                    "timestamp": timestamp,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 100.0,
                    "atr": 1.0,
                    "rsi": 50.0,
                    "vol_ma": 100.0,
                    "roc": 0.01,
                    "body_atr_ratio": 0.5,
                    "return_zscore": 0.5,
                    "higher_tf_ema": 100.0,
                    "higher_tf_slope_atr_ratio": 1.5,
                    "trend_regime": "sideways",
                }
            )

        rows[-2].update(
            {
                "close": 102.6,
                "volume": 300.0,
                "rsi": 84.0,
                "roc": 0.04,
                "body_atr_ratio": 2.5,
                "return_zscore": 3.0,
                "trend_regime": "uptrend",
            }
        )
        rows[-1].update(
            {
                "close": 102.0,
                "volume": 280.0,
                "rsi": 82.0,
                "roc": 0.02,
                "body_atr_ratio": 2.1,
                "return_zscore": 2.4,
                "trend_regime": "uptrend",
            }
        )

        signal = strategy.check_entry_signal(pd.DataFrame(rows))

        self.assertIsNone(signal)


class ClosePositionTest(unittest.TestCase):
    def test_close_position_updates_balance_and_trade_log(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.CONFIG.update(
            {
                "maker_fee_rate": 0.0,
                "taker_fee_rate": 0.0,
                "maker_slippage_bps": 0.0,
                "taker_slippage_bps": 0.0,
            }
        )
        logs: list[str] = []
        strategy.log_event = lambda msg: logs.append(msg)
        strategy.current_position = {
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 2.0,
            "stop_loss": 98.0,
            "entry_time": 10,
            "highest_price": 103.0,
            "lowest_price": 100.0,
        }

        trade = strategy.close_position(103.0, "测试平仓", exit_time=70)

        self.assertIsNone(strategy.current_position)
        self.assertAlmostEqual(strategy.account_balance, 1006.0, places=6)
        self.assertEqual(len(strategy.trade_log), 1)
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(trade["net_pnl"], 6.0, places=6)
        self.assertEqual(trade["exit_time"], 70)
        self.assertTrue(any("净盈亏 6.0000" in msg for msg in logs))


class ExecutionCostModelTest(unittest.TestCase):
    def test_open_and_close_position_apply_slippage_and_fee_model(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.CONFIG.update(
            {
                "entry_order_type": "taker",
                "exit_order_type": "maker",
                "maker_fee_rate": 0.0002,
                "taker_fee_rate": 0.001,
                "maker_slippage_bps": 0.0,
                "taker_slippage_bps": 10.0,
            }
        )
        strategy.log_event = lambda msg: None

        position = strategy.open_position(
            "BUY",
            {"timestamp": 0, "close": 100.0, "atr": 1.0},
        )
        trade = strategy.close_position(102.0, "测试平仓", exit_time=60)

        self.assertIsNotNone(position)
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(position["entry_price"], 100.1, places=6)
        self.assertAlmostEqual(position["entry_fee"], 0.5005, places=6)
        self.assertAlmostEqual(trade["exit_price"], 102.0, places=6)
        self.assertAlmostEqual(trade["exit_fee"], 0.102, places=6)
        self.assertAlmostEqual(trade["net_pnl"], 8.8975, places=6)
        self.assertAlmostEqual(strategy.account_balance, 1008.8975, places=6)


class BacktestTest(unittest.TestCase):
    def test_run_backtest_returns_equity_curve_and_summary(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.CONFIG.update(
            {
                "maker_fee_rate": 0.0,
                "taker_fee_rate": 0.0,
                "maker_slippage_bps": 0.0,
                "taker_slippage_bps": 0.0,
            }
        )
        strategy.log_event = lambda msg: None
        strategy.get_min_required_bars = lambda: 2

        def fake_calculate_indicators(df):
            df = df.copy()
            df["atr"] = 1.0
            df["rsi"] = 50.0
            df["vol_ma"] = 100.0
            df["roc"] = 0.0
            df["body_atr_ratio"] = 0.0
            df["return_zscore"] = 0.0
            return df

        strategy.calculate_indicators = fake_calculate_indicators
        strategy.check_entry_signal = lambda df, end_idx=None: "BUY" if (end_idx if end_idx is not None else len(df) - 1) == 1 else None

        market_data = [
            {
                "timestamp": 0,
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 100.0,
            },
            {
                "timestamp": 60,
                "open": 100.0,
                "high": 101.5,
                "low": 99.8,
                "close": 101.0,
                "volume": 100.0,
            },
            {
                "timestamp": 120,
                "open": 101.0,
                "high": 102.2,
                "low": 100.9,
                "close": 102.0,
                "volume": 100.0,
            },
            {
                "timestamp": 180,
                "open": 102.0,
                "high": 102.1,
                "low": 101.0,
                "close": 101.4,
                "volume": 100.0,
            },
        ]

        result = strategy.run_backtest(market_data)

        self.assertEqual(result["summary"]["total_trades"], 1)
        self.assertAlmostEqual(result["summary"]["final_balance"], 1002.0, places=6)
        self.assertAlmostEqual(result["summary"]["final_equity"], 1002.0, places=6)
        self.assertEqual(len(result["equity_curve"]), len(market_data))
        self.assertFalse(result["equity_curve"][-1]["in_position"])
        self.assertAlmostEqual(result["equity_curve"][-1]["equity"], 1002.0, places=6)
        self.assertEqual(result["trades"][0]["reason"], "追踪止盈回撤")

    def test_run_backtest_can_export_summary_trades_and_equity_curve(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.CONFIG.update(
            {
                "maker_fee_rate": 0.0,
                "taker_fee_rate": 0.0,
                "maker_slippage_bps": 0.0,
                "taker_slippage_bps": 0.0,
            }
        )
        strategy.log_event = lambda msg: None
        strategy.get_min_required_bars = lambda: 2

        def fake_calculate_indicators(df):
            df = df.copy()
            df["atr"] = 1.0
            df["rsi"] = 50.0
            df["vol_ma"] = 100.0
            df["roc"] = 0.0
            df["body_atr_ratio"] = 0.0
            df["return_zscore"] = 0.0
            df["higher_tf_ema"] = 100.0
            df["higher_tf_slope_atr_ratio"] = 0.0
            df["trend_regime"] = "sideways"
            return df

        strategy.calculate_indicators = fake_calculate_indicators
        strategy.check_entry_signal = lambda df, end_idx=None: "BUY" if (end_idx if end_idx is not None else len(df) - 1) == 1 else None
        market_data = [
            {
                "timestamp": 0,
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 100.0,
            },
            {
                "timestamp": 60,
                "open": 100.0,
                "high": 101.5,
                "low": 99.8,
                "close": 101.0,
                "volume": 100.0,
            },
            {
                "timestamp": 120,
                "open": 101.0,
                "high": 102.2,
                "low": 100.9,
                "close": 102.0,
                "volume": 100.0,
            },
            {
                "timestamp": 180,
                "open": 102.0,
                "high": 102.1,
                "low": 101.0,
                "close": 101.4,
                "volume": 100.0,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            result = strategy.run_backtest(
                market_data,
                export_dir=temp_dir,
                export_prefix="unit_test",
            )

            exports = result["exports"]
            summary_path = Path(exports["summary"])
            trades_path = Path(exports["trades"])
            equity_curve_path = Path(exports["equity_curve"])

            self.assertTrue(summary_path.exists())
            self.assertTrue(trades_path.exists())
            self.assertTrue(equity_curve_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_trades"], 1)
            self.assertAlmostEqual(summary["final_equity"], 1002.0, places=6)

            trades_df = pd.read_csv(trades_path)
            equity_curve_df = pd.read_csv(equity_curve_path)
            self.assertEqual(len(trades_df), 1)
            self.assertIn("net_pnl", trades_df.columns)
            self.assertEqual(len(equity_curve_df), len(market_data))
            self.assertIn("drawdown_pct", equity_curve_df.columns)


class ParameterSearchTest(unittest.TestCase):
    def test_run_parameter_scan_ranks_best_config(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.run_backtest_with_config = lambda market_data, config_override=None, **kwargs: {
            "summary": {"final_equity": 1000.0 + float(config_override["body_atr_threshold"])}
        }

        result = strategy.run_parameter_scan(
            market_data=[{"timestamp": 0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
            parameter_grid={"body_atr_threshold": [1.5, 2.0, 2.5]},
        )

        self.assertEqual(result["best"]["config_override"]["body_atr_threshold"], 2.5)
        self.assertEqual(result["results"][0]["rank"], 1)
        self.assertEqual(len(result["results"]), 3)

    def test_run_walk_forward_selects_config_and_stitches_segments(self) -> None:
        module = load_module()
        strategy = module.SpringReversionStrategy()
        strategy.log_event = lambda msg: None

        def fake_run_backtest_with_config(market_data, config_override=None, **kwargs):
            data_length = len(market_data)
            score_bias = float(config_override["body_atr_threshold"])
            if data_length == 4:
                return {"summary": {"final_equity": 1000.0 + score_bias}}

            starting_balance = float(kwargs["starting_balance"])
            final_balance = starting_balance + score_bias
            return {
                "summary": {
                    "final_balance": final_balance,
                    "final_equity": final_balance,
                },
                "trades": [
                    {
                        "net_pnl": score_bias,
                        "reason": "walk_forward",
                    }
                ],
                "equity_curve": [
                    {
                        "timestamp": int(market_data[0]["timestamp"]),
                        "close": float(market_data[0]["close"]),
                        "balance": final_balance,
                        "equity": final_balance,
                        "unrealized_pnl": 0.0,
                        "gross_open_pnl": 0.0,
                        "estimated_exit_price": float(market_data[0]["close"]),
                        "estimated_exit_fee": 0.0,
                        "in_position": False,
                        "position_side": None,
                    }
                ],
            }

        strategy.run_backtest_with_config = fake_run_backtest_with_config
        market_data = [
            {"timestamp": idx, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 100.0}
            for idx in range(10)
        ]

        result = strategy.run_walk_forward(
            market_data=market_data,
            parameter_grid={"body_atr_threshold": [1.0, 2.0]},
            train_bars=4,
            test_bars=2,
            step_bars=2,
            starting_balance=1000.0,
        )

        self.assertEqual(result["summary"]["segments"], 3)
        self.assertAlmostEqual(result["summary"]["final_balance"], 1006.0, places=6)
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(result["segments"][0]["selected_config"]["body_atr_threshold"], 2.0)
        self.assertEqual(len(result["trades"]), 3)


if __name__ == "__main__":
    unittest.main()
