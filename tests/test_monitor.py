# -*- coding: utf-8 -*-

import unittest

from services.monitor import MonitorService


class TestMonitorChargeDynamic(unittest.TestCase):
    def test_is_charge_dynamic_by_additional_type(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "additional": {
                        "type": "ONLYFANS",
                    }
                }
            }
        }
        self.assertTrue(MonitorService.is_charge_dynamic(item))

    def test_is_charge_dynamic_by_badge_text(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "major": {
                        "opus": {
                            "badge": {"text": "充电专属"},
                        }
                    }
                }
            }
        }
        self.assertTrue(MonitorService.is_charge_dynamic(item))

    def test_is_charge_dynamic_false_when_no_signals(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "major": {"type": "OPUS"},
                }
            }
        }
        self.assertFalse(MonitorService.is_charge_dynamic(item))


if __name__ == "__main__":
    unittest.main()
