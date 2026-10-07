"""Stemquill's window. The audio work lives in stemquill.core; this package is only the interface."""

from .app import run_gui

__all__ = ["run_gui"]
