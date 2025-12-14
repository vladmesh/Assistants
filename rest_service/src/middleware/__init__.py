"""Middleware modules for REST service."""

from .correlation import CorrelationIdMiddleware

__all__ = ["CorrelationIdMiddleware"]
