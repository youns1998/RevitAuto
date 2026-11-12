# -*- coding: utf-8 -*-
"""Run portable tests with a regular Python 3 interpreter; no pyRevit required."""
import os
import sys
import unittest

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, 'RevitAuto.extension', 'lib'))
suite = unittest.defaultTestLoader.discover(os.path.join(root, 'tests'), pattern='test_*.py')
sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
