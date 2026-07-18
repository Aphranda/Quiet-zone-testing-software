from __future__ import annotations

import numpy as np


def signed_add(*values_db: np.ndarray | float) -> np.ndarray:
    """Add signed dB-domain arrays/scalars point by point."""
    arrays = [np.asarray(value, dtype=float) for value in values_db]
    if not arrays:
        raise ValueError("At least one value is required.")
    result = arrays[0].copy()
    for value in arrays[1:]:
        result = result + value
    return result


def deembed_standard_horn(s21_raw_db: np.ndarray | float, horn_gain_dbi: np.ndarray | float) -> np.ndarray:
    """Remove positive standard horn gain from a signed S21-style link value."""
    return np.asarray(s21_raw_db, dtype=float) - np.asarray(horn_gain_dbi, dtype=float)


def aux_loss(s21_aux_raw_db: np.ndarray | float) -> np.ndarray:
    return -np.asarray(s21_aux_raw_db, dtype=float)


def link_cal_001_h(s21_raw_db: np.ndarray, l_aux_a_db: np.ndarray, l_aux_c_db: np.ndarray, horn_gain_h_dbi: np.ndarray) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_a_db, l_aux_c_db, -np.asarray(horn_gain_h_dbi, dtype=float))


def link_cal_001_v(s21_raw_db: np.ndarray, l_aux_b_db: np.ndarray, l_aux_c_db: np.ndarray, horn_gain_v_dbi: np.ndarray) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_b_db, l_aux_c_db, -np.asarray(horn_gain_v_dbi, dtype=float))


def link_cal_001_dut(s21_raw_db: np.ndarray, l_aux_a_db: np.ndarray, l_aux_c_db: np.ndarray) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_a_db, l_aux_c_db)


def link_cal_001_feed(l_ch_int_h_db: np.ndarray, l_ch_int_v_db: np.ndarray, l_ch_int_dut_db: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray(l_ch_int_h_db, dtype=float) - np.asarray(l_ch_int_dut_db, dtype=float),
        np.asarray(l_ch_int_v_db, dtype=float) - np.asarray(l_ch_int_dut_db, dtype=float),
    )


def link_cal_002_dut_vna(s21_raw_db: np.ndarray | float, l_aux_d_db: np.ndarray | float) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_d_db)


def link_cal_002_vna_feed(
    l_vna_db: np.ndarray | float,
    horn_gain_db: np.ndarray | float,
    l_dut_vna_db: np.ndarray | float,
) -> np.ndarray:
    return signed_add(l_vna_db, -np.asarray(horn_gain_db, dtype=float), -np.asarray(l_dut_vna_db, dtype=float))


def link_cal_003_dut_sa(t_auxe_dut_sa_db: np.ndarray | float, l_aux_e_db: np.ndarray | float) -> np.ndarray:
    return signed_add(t_auxe_dut_sa_db, l_aux_e_db)


def link_cal_004_system_tx_sa(t_sys_tx_sa_db: np.ndarray | float, horn_gain_db: np.ndarray | float, l_dut_vna_db: np.ndarray | float) -> np.ndarray:
    return signed_add(t_sys_tx_sa_db, -np.asarray(horn_gain_db, dtype=float), -np.asarray(l_dut_vna_db, dtype=float))


def link_cal_004_dut_vna_f(s21_raw_db: np.ndarray | float, l_aux_f_db: np.ndarray | float) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_f_db)


def link_cal_005_dut_vna_g(s21_raw_db: np.ndarray | float, l_aux_g_db: np.ndarray | float) -> np.ndarray:
    return signed_add(s21_raw_db, l_aux_g_db)


def link_cal_005_sg(
    t_sg_db: np.ndarray | float,
    horn_gain_db: np.ndarray | float,
    l_dut_vna_g_db: np.ndarray | float,
) -> np.ndarray:
    return signed_add(t_sg_db, -np.asarray(horn_gain_db, dtype=float), -np.asarray(l_dut_vna_g_db, dtype=float))


def feed_loss(ch_int_db: np.ndarray, ch_int_dut_db: np.ndarray) -> np.ndarray:
    return np.asarray(ch_int_db, dtype=float) - np.asarray(ch_int_dut_db, dtype=float)
