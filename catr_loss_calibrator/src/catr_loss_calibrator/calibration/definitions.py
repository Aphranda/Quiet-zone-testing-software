from __future__ import annotations

from catr_loss_calibrator.calibration.models import (
    CalibrationCatalog,
    CalibrationItem,
    CalibrationStep,
    MeasurementRole,
)


def default_calibration_catalog() -> CalibrationCatalog:
    return CalibrationCatalog(
        items=(
            _link_cal_001(),
            _link_cal_002(),
            _link_cal_003(),
            _link_cal_004(),
            _link_cal_005(),
        )
    )


def _link_cal_001() -> CalibrationItem:
    return CalibrationItem(
        id="LINK-CAL-001",
        name="暗室内部链路校准",
        purpose="校准暗室 H/V 经馈源、反射面、标准增益喇叭到 DUT 口，以及转台 DUT 到接口板 DUT 段。",
        steps=(
            CalibrationStep(
                id="CAL001-AUX",
                name="AUX-A/B/C 独立测试",
                role=MeasurementRole.VNA_S21,
                input_port="P1/P2",
                output_port="P1/P2",
                manual_instruction="逐根将 AUX-A、AUX-B、AUX-C 直连 VNA PORT1/PORT2。",
                raw_outputs=("S21_AUX_A", "S21_AUX_B", "S21_AUX_C"),
                final_outputs=("L_AUX_A", "L_AUX_B", "L_AUX_C"),
                notes="L_AUX_* 按带符号 S21 保存，通常为负数。",
            ),
            CalibrationStep(
                id="CAL001-H",
                name="DUT-H 闭合测量",
                role=MeasurementRole.VNA_S21,
                input_port="P1",
                output_port="P2",
                manual_instruction="PORT1 -> AUX-A -> CP-H；CP-DUT -> AUX-C -> PORT2。",
                raw_outputs=("S21_CH_INT_H_RAW",),
                final_outputs=("L_CH_INT_H",),
                required_inputs=("L_AUX_A", "L_AUX_C", "G_STD_HORN_H"),
            ),
            CalibrationStep(
                id="CAL001-V",
                name="DUT-V 闭合测量",
                role=MeasurementRole.VNA_S21,
                input_port="P1",
                output_port="P2",
                manual_instruction="PORT1 -> AUX-B -> CP-V；CP-DUT -> AUX-C -> PORT2。",
                raw_outputs=("S21_CH_INT_V_RAW",),
                final_outputs=("L_CH_INT_V",),
                required_inputs=("L_AUX_B", "L_AUX_C", "G_STD_HORN_V"),
            ),
            CalibrationStep(
                id="CAL001-DUT",
                name="转台 DUT 到暗室接口板 DUT",
                role=MeasurementRole.VNA_S21,
                input_port="P1",
                output_port="P2",
                manual_instruction="PORT1 -> AUX-A -> 转台DUT接口；CP-DUT -> AUX-C -> PORT2。",
                raw_outputs=("S21_CH_INT_DUT_RAW",),
                final_outputs=("L_CH_INT_DUT", "L_CH_INT_FEED_H", "L_CH_INT_FEED_V"),
                required_inputs=("L_AUX_A", "L_AUX_C", "L_CH_INT_H", "L_CH_INT_V"),
            ),
        ),
    )


def _link_cal_002() -> CalibrationItem:
    return CalibrationItem(
        id="LINK-CAL-002",
        name="VNA 链路损耗校准",
        purpose="校准 VNA1 经 H/V 空间链路到 VNA2 的测试链路，并校准 DUT 到 VNA2 回传段。",
        steps=(
            CalibrationStep(
                id="CAL002-AUX-D",
                name="AUX-D 独立测试",
                role=MeasurementRole.VNA_S21,
                input_port="P1/P2",
                output_port="P1/P2",
                manual_instruction="AUX-D 直连 VNA PORT1/PORT2。",
                raw_outputs=("S21_AUX_D",),
                final_outputs=("L_AUX_D",),
            ),
            CalibrationStep(
                id="CAL002-DUT-VNA2",
                name="DUT 到 VNA2 回传段",
                role=MeasurementRole.VNA_S21,
                input_port="TD",
                output_port="LB-VNA2",
                manual_instruction="PORT1 -> AUX-D -> 转台DUT接口；链路箱 DUT 到 VNA2。",
                route_ids=("DUT_VNA2",),
                link_commands=("CONFigure:LINK DUT, VNA2",),
                raw_outputs=("S21_DUT_VNA_RAW",),
                final_outputs=("L_DUT_VNA",),
                required_inputs=("L_AUX_D",),
            ),
            CalibrationStep(
                id="CAL002-DUT-AMP1-VNA2",
                name="DUT 经 AMP1 到 VNA2 回传段",
                role=MeasurementRole.VNA_S21,
                input_port="TD",
                output_port="LB-VNA2",
                manual_instruction="PORT1 -> AUX-D -> 转台DUT接口；链路箱 DUT 经 AMP1 到 VNA2。",
                route_ids=("DUT_AMP1_VNA2",),
                link_commands=("CONFigure:LINK DUT, AMP1, VNA2",),
                raw_outputs=("S21_DUT_VNA_AMP1_RAW",),
                final_outputs=("L_DUT_VNA_AMP1",),
                required_inputs=("L_AUX_D",),
            ),
            CalibrationStep(
                id="CAL002-MAIN",
                name="VNA 主链路三工况",
                role=MeasurementRole.VNA_S21,
                input_port="LB-VNA1",
                output_port="LB-VNA2",
                manual_instruction="转台 DUT 位置换标准增益喇叭，按 H/V 与三种工况采样。",
                route_ids=("DUT_VNA2", "DUT_AMP1_VNA2", "H_AMP2_VNA1", "V_AMP2_VNA1"),
                link_commands=(
                    "CONFigure:LINK DUT, VNA2",
                    "CONFigure:LINK H/V, VNA1",
                    "CONFigure:LINK DUT, AMP1, VNA2",
                    "CONFigure:LINK H/V, VNA1",
                    "CONFigure:LINK DUT, VNA2",
                    "CONFigure:LINK H/V, AMP2, VNA1",
                ),
                raw_outputs=("L_VNA_H/V", "L_VNA_H/V_AMP1", "L_VNA_H/V_AMP2"),
                final_outputs=("L_VNA_FEED_H/V", "L_VNA_FEED_H/V_AMP1", "L_VNA_FEED_H/V_AMP2"),
                required_inputs=("G_STD_HORN_H/V", "L_DUT_VNA", "L_DUT_VNA_AMP1"),
            ),
        ),
    )


def _link_cal_003() -> CalibrationItem:
    return CalibrationItem(
        id="LINK-CAL-003",
        name="DUT 到 SA 校准",
        purpose="校准 DUT 参考面到 SA 的直通/AMP1 接收链路，供 G/T 等 DUT→SA 场景使用。",
        steps=(
            CalibrationStep(
                id="CAL003-AUX-E",
                name="AUX-E 独立测试",
                role=MeasurementRole.VNA_S21,
                input_port="P1/P2",
                output_port="P1/P2",
                manual_instruction="AUX-E 直连 VNA PORT1/PORT2。",
                raw_outputs=("S21_AUX_E",),
                final_outputs=("L_AUX_E",),
            ),
            CalibrationStep(
                id="CAL003-DUT-SA",
                name="DUT 到 SA 主输出",
                role=MeasurementRole.VNA_S21,
                input_port="DUT_REF",
                output_port="LB-SA",
                manual_instruction="PORT1 -> AUX-E -> 转台DUT接口；PORT2 接链路箱 SA。",
                route_ids=("DUT_SA", "DUT_AMP1_SA"),
                link_commands=("CONFigure:LINK DUT, SA", "CONFigure:LINK DUT, AMP1, SA"),
                raw_outputs=("T_AUXE_DUT_SA", "T_AUXE_DUT_SA_AMP1"),
                final_outputs=("L_DUT_SA", "L_DUT_SA_AMP1"),
                required_inputs=("L_AUX_E",),
            ),
        ),
    )


def _link_cal_004() -> CalibrationItem:
    return CalibrationItem(
        id="LINK-CAL-004",
        name="SA-H/V 校准",
        purpose="校准整机发射场景中 H/V 馈源侧到 SA 的直通/AMP2 接收链路。",
        steps=(
            CalibrationStep(
                id="CAL004-SA-HV-THRU",
                name="SA-H/V 直通接收链路",
                role=MeasurementRole.VNA_S21,
                input_port="LB-SA",
                output_port="LB-VNA2",
                manual_instruction="标准增益喇叭替代 DUT；PORT1 接 SA，PORT2 接 VNA2。",
                route_ids=("H_SA", "V_SA"),
                link_commands=("CONFigure:LINK H/V, SA", "CONFigure:LINK DUT, VNA2"),
                raw_outputs=("T_SYS_TX_SA_H/V",),
                final_outputs=("L_SYS_TX_SA_H/V",),
                required_inputs=("G_STD_HORN_H/V", "L_DUT_VNA"),
            ),
            CalibrationStep(
                id="CAL004-SA-HV-AMP2",
                name="SA-H/V 经 AMP2 接收链路",
                role=MeasurementRole.VNA_S21,
                input_port="LB-VNA2",
                output_port="LB-SA",
                manual_instruction="标准增益喇叭替代 DUT；PORT1 接 VNA2，PORT2 接 SA，保证 S21 沿 H/V→AMP2→SA 方向。",
                route_ids=("H_AMP2_SA", "V_AMP2_SA"),
                link_commands=("CONFigure:LINK H/V, AMP2, SA", "CONFigure:LINK DUT, VNA2"),
                raw_outputs=("T_SYS_TX_SA_H/V_AMP2",),
                final_outputs=("L_SYS_TX_SA_H/V_AMP2",),
                required_inputs=("G_STD_HORN_H/V", "L_DUT_VNA"),
            ),
            CalibrationStep(
                id="CAL004-SA-HV-DUTAMP1-CHECK",
                name="SA-H/V DUT 侧 AMP1 一致性校验",
                role=MeasurementRole.VNA_S21,
                input_port="LB-SA",
                output_port="LB-VNA2",
                manual_instruction="标准增益喇叭替代 DUT；PORT1 接 SA，PORT2 接 VNA2。",
                route_ids=("DUT_AMP1_VNA2",),
                link_commands=("CONFigure:LINK H/V, SA", "CONFigure:LINK DUT, AMP1, VNA2"),
                raw_outputs=("T_SYS_TX_SA_H/V_DUTAMP1",),
                required_inputs=("G_STD_HORN_H/V", "L_DUT_VNA_AMP1"),
                notes="该工况用于一致性校验，不作为整机发射默认正式输出。",
            ),
        ),
    )


def _link_cal_005() -> CalibrationItem:
    return CalibrationItem(
        id="LINK-CAL-005",
        name="SG 校准",
        purpose="校准 SG 到 DUT 参考面的等效发射链路，使用 AUX-F 重复测回传段。",
        steps=(
            CalibrationStep(
                id="CAL005-AUX-F",
                name="AUX-F 独立测试",
                role=MeasurementRole.VNA_S21,
                input_port="P1/P2",
                output_port="P1/P2",
                manual_instruction="AUX-F 直连 VNA PORT1/PORT2。",
                raw_outputs=("S21_AUX_F",),
                final_outputs=("L_AUX_F",),
            ),
            CalibrationStep(
                id="CAL005-DUT-VNA2",
                name="AUX-F 回传段",
                role=MeasurementRole.VNA_S21,
                input_port="TD",
                output_port="LB-VNA2",
                manual_instruction="PORT1 -> AUX-F -> 转台DUT接口；PORT2 接 VNA2。",
                route_ids=("DUT_VNA2", "DUT_AMP1_VNA2"),
                link_commands=("CONFigure:LINK DUT, VNA2", "CONFigure:LINK DUT, AMP1, VNA2"),
                raw_outputs=("S21_DUT_VNA_F_RAW", "S21_DUT_VNA_F_AMP1_RAW"),
                final_outputs=("L_DUT_VNA_F", "L_DUT_VNA_F_AMP1"),
                required_inputs=("L_AUX_F",),
            ),
            CalibrationStep(
                id="CAL005-SG",
                name="SG 三工况",
                role=MeasurementRole.VNA_S21,
                input_port="LB-SG/LB-VNA2",
                output_port="DUT_REF",
                manual_instruction="直通/AMP1：PORT1 接 SG、PORT2 接 VNA2；AMP2：PORT1 接 VNA2、PORT2 接 SG，转台 DUT 位置为标准增益喇叭。",
                route_ids=("H_SG", "V_SG", "H_AMP2_SG", "V_AMP2_SG"),
                link_commands=(
                    "CONFigure:LINK H/V, SG",
                    "CONFigure:LINK DUT, VNA2",
                    "CONFigure:LINK H/V, SG",
                    "CONFigure:LINK DUT, AMP1, VNA2",
                    "CONFigure:LINK H/V, AMP2, SG",
                    "CONFigure:LINK DUT, VNA2",
                ),
                raw_outputs=("T_SG_H/V", "T_SG_H/V_AMP1", "T_SG_H/V_AMP2"),
                final_outputs=("L_SG_DUT_H/V", "L_SG_DUT_H/V_AMP1", "L_HV_SG_H/V_AMP2"),
                required_inputs=("G_STD_HORN_H/V", "L_DUT_VNA_F", "L_DUT_VNA_F_AMP1"),
            ),
        ),
    )
