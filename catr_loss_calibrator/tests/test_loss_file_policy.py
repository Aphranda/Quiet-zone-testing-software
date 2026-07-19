from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy
from catr_loss_calibrator.storage.loss_file_policy import band_entries_from_config


def test_feed_horn_band_intersections() -> None:
    policy = LossFilePolicy()
    assert policy.band_for("F10_17G", "H10_15G") == "10_15G"
    assert policy.band_for("F10_17G", "H14P5_22G") == "14P5_17G"
    assert policy.band_for("F17_31G", "H14P5_22G") == "17_22G"
    assert policy.band_for("F17_31G", "H21P7_33G") == "21P7_31G"


def test_loss_filename() -> None:
    policy = LossFilePolicy()
    assert (
        policy.filename(param="L_VNA_FEED_H", band="10_15G", feed="F10_17G", horn="H10_15G")
        == "L_VNA_FEED_H_10_15G_F10_17G_H10_15G.csv"
    )


def test_loss_filename_for_uses_intersection_band() -> None:
    policy = LossFilePolicy()
    assert policy.filename_for(param="L_VNA_FEED_H", feed="F10_17G", horn="H10_15G") == "L_VNA_FEED_H_10_15G_F10_17G_H10_15G.csv"


def test_loss_file_policy_accepts_project_band_config() -> None:
    band_config = {
        "feed_horn_bands": [
            {
                "feed": "F_CUSTOM",
                "horn": "H_CUSTOM",
                "band": "33_40G",
                "horn_gain_file": "resources/H_CUSTOM.csv",
            },
        ]
    }
    policy = LossFilePolicy.from_band_config(band_config)

    assert policy.band_for("F_CUSTOM", "H_CUSTOM") == "33_40G"
    assert policy.filename_for(param="L_SYS", feed="F_CUSTOM", horn="H_CUSTOM") == "L_SYS_33_40G_F_CUSTOM_H_CUSTOM.csv"
    assert band_entries_from_config(band_config)[0]["horn_gain_file"] == "resources/H_CUSTOM.csv"


def test_validate_feed_horn_rejects_invalid_pair() -> None:
    policy = LossFilePolicy()
    try:
        policy.validate_feed_horn("F10_17G", "H21P7_33G")
    except ValueError as exc:
        assert "No valid band intersection" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
