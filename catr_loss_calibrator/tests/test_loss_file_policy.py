from catr_loss_calibrator.storage.loss_file_policy import LossFilePolicy


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


def test_validate_feed_horn_rejects_invalid_pair() -> None:
    policy = LossFilePolicy()
    try:
        policy.validate_feed_horn("F10_17G", "H21P7_33G")
    except ValueError as exc:
        assert "No valid band intersection" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
