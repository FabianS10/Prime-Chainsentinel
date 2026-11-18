"""Tres pruebas unitarias de cálculo financiero, sin base, reloj, red ni archivos."""
import numpy as np
import pytest

from app.services.model_compare import _pinball_loss, _simulate_terminal_values
from app.services.portfolio import normalize_weights


def test_pesos_relativos():
    assert normalize_weights(np.array([1.0, 3.0])) == pytest.approx([0.25, 0.75])


def test_perdida_cuantilica_asimetrica():
    assert _pinball_loss(120, 100, 0.10) == pytest.approx(2.0)
    assert _pinball_loss(80, 100, 0.10) == pytest.approx(18.0)
    assert _pinball_loss(100, 100, 0.10) == 0.0


def test_aporte_antes_del_retorno():
    monthly = np.array([[0.10, -0.10], [0.0, 0.0]])
    terminal = _simulate_terminal_values(monthly, initial_capital=100, monthly_contribution=10)
    assert terminal == pytest.approx([117.9, 120.0])
