"""Backtest engine: replay a strategy over past scan dates and simulate every pick with the Tracker's rules.
Pure: no database, no HTTP. services/backtest_service.py supplies data and persists results.
"""
