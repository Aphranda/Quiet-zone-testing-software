import numpy as np
from pathlib import Path

from catr_loss_calibrator.calibration.formulas import (
    aux_loss,
    deembed_standard_horn,
    feed_loss,
    link_cal_001_feed,
    link_cal_001_dut,
    link_cal_001_h,
    link_cal_002_dut_vna,
    link_cal_002_vna_feed,
    link_cal_003_dut_sa,
    link_cal_004_dut_vna_f,
    link_cal_004_system_tx_sa,
    link_cal_005_dut_vna_g,
    link_cal_005_sg,
)


def test_aux_values_are_signed_and_added_directly() -> None:
    s21 = np.array([-80.0])
    aux_a = np.array([-1.0])
    aux_c = np.array([-2.0])
    horn = np.array([20.0])
    assert np.allclose(link_cal_001_h(s21, aux_a, aux_c, horn), np.array([-103.0]))


def test_dut_internal_segment_does_not_deembed_horn() -> None:
    assert np.allclose(
        link_cal_001_dut(np.array([-10.0]), np.array([-1.0]), np.array([-2.0])),
        np.array([-13.0]),
    )


def test_feed_loss_subtracts_dut_segment() -> None:
    assert np.allclose(feed_loss(np.array([-103.0]), np.array([-13.0])), np.array([-90.0]))


def test_aux_loss_turns_raw_s21_into_positive_loss() -> None:
    assert np.allclose(aux_loss(np.array([-3.5])), np.array([3.5]))


def test_deembed_standard_horn_keeps_full_loop_except_horn_gain() -> None:
    assert np.allclose(deembed_standard_horn(np.array([-70.0]), np.array([20.0])), np.array([-90.0]))


def test_link_cal_001_feed_uses_signed_subtraction() -> None:
    h, v = link_cal_001_feed(np.array([-103.0]), np.array([-99.0]), np.array([-13.0]))
    assert np.allclose(h, np.array([-90.0]))
    assert np.allclose(v, np.array([-86.0]))


def test_link_cal_002_dut_vna_and_vna_feed() -> None:
    dut_vna = link_cal_002_dut_vna(np.array([-80.0]), np.array([3.0]))
    assert np.allclose(dut_vna, np.array([-77.0]))
    vna_feed = link_cal_002_vna_feed(np.array([-100.0]), np.array([20.0]), dut_vna)
    assert np.allclose(vna_feed, np.array([-43.0]))


def test_link_cal_003_dut_sa() -> None:
    assert np.allclose(link_cal_003_dut_sa(np.array([-40.0]), np.array([5.0])), np.array([-35.0]))


def test_link_cal_004_system_tx_sa() -> None:
    assert np.allclose(
        link_cal_004_system_tx_sa(np.array([-70.0]), np.array([20.0]), np.array([-80.0])),
        np.array([-10.0]),
    )


def test_link_cal_004_dut_vna_f() -> None:
    dut_vna_f = link_cal_004_dut_vna_f(np.array([-60.0]), np.array([2.0]))
    assert np.allclose(dut_vna_f, np.array([-58.0]))


def test_link_cal_005_dut_vna_g_and_sg() -> None:
    dut_vna_g = link_cal_005_dut_vna_g(np.array([-60.0]), np.array([2.0]))
    assert np.allclose(dut_vna_g, np.array([-58.0]))
    assert np.allclose(link_cal_005_sg(np.array([-90.0]), np.array([20.0]), dut_vna_g), np.array([-52.0]))


def test_formula_module_does_not_define_aux_corr_or_positive_aux_conversion() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "catr_loss_calibrator" / "calibration" / "formulas.py"
    source = source.read_text(encoding="utf-8")
    assert "AUX_CORR" not in source
    assert "aux_corr" not in source
    assert "abs(" not in source
