# -*- coding: utf-8 -*-
"""
Regression tests for Hong Kong realtime quote routing.
"""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()
if "json_repair" not in sys.modules:
    sys.modules["json_repair"] = MagicMock()

from data_provider.base import DataFetcherManager


class _DummyFetcher:
    def __init__(self, name: str, priority: int, result=None):
        self.name = name
        self.priority = priority
        self.result = result
        self.calls = []

    def get_realtime_quote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def _complete_quote():
    quote = SimpleNamespace(
        volume_ratio=1.1,
        turnover_rate=2.0,
        pe_ratio=20.0,
        pb_ratio=3.0,
        total_mv=100.0,
        circ_mv=80.0,
        amplitude=1.5,
    )
    quote.has_basic_data = lambda: True
    return quote


class TestHKRealtimeRouting(unittest.TestCase):
    """Ensure HK realtime lookup does not fan out into A-share sources."""

    @patch("src.config.get_config")
    def test_manager_routes_hk_suffix_only_to_akshare_once(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina,efinance,akshare_em,tushare",
        )

        efinance = _DummyFetcher("EfinanceFetcher", 0, result={"should": "not be called"})
        akshare = _DummyFetcher("AkshareFetcher", 1, result=None)
        tushare = _DummyFetcher("TushareFetcher", 2, result={"should": "not be called"})

        manager = DataFetcherManager(fetchers=[efinance, akshare, tushare])
        quote = manager.get_realtime_quote("1810.HK")

        self.assertIsNone(quote)
        self.assertEqual(akshare.calls, [(("HK01810",), {"source": "hk"})])
        self.assertEqual(efinance.calls, [])
        self.assertEqual(tushare.calls, [])

    @patch("src.config.get_config")
    def test_manager_respects_hk_specific_source_priority(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina",
            hk_realtime_source_priority="akshare_hk,longbridge",
        )
        akshare = _DummyFetcher("AkshareFetcher", 1, result=_complete_quote())
        longbridge = _DummyFetcher("LongbridgeFetcher", 5, result=_complete_quote())

        manager = DataFetcherManager(fetchers=[akshare, longbridge])
        quote = manager.get_realtime_quote("00700")

        self.assertIsNotNone(quote)
        self.assertEqual(akshare.calls, [(("HK00700",), {"source": "hk"})])
        self.assertEqual(longbridge.calls, [])

    def test_hk_source_priority_rejects_unknown_and_deduplicates(self):
        self.assertEqual(
            DataFetcherManager._resolve_hk_realtime_sources(
                "unknown,akshare_hk,akshare_hk,longbridge"
            ),
            ["akshare_hk", "longbridge"],
        )


if __name__ == "__main__":
    unittest.main()
