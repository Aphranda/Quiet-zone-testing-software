import numpy as np

from catr_loss_calibrator.calibration.formulas import (
    feed_loss,
    link_cal_001_dut,
    link_cal_001_h,
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
