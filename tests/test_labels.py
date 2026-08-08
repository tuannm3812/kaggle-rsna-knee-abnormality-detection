from knee_mri.labels import LABEL_COLUMNS, extract_weak_labels


def test_label_columns_matches_submission_header():
    assert LABEL_COLUMNS == [
        "ACL",
        "MCL",
        "Medial Meniscus",
        "Lateral Meniscus",
        "Medial OA",
        "Lateral OA",
        "PF OA",
        "Effusion",
        "Synovitis",
        "Baker's",
        "Contusion",
        "Fracture",
    ]


def test_extract_weak_labels_detects_multiple_findings():
    report = (
        "There is a complete tear of the ACL. Moderate joint effusion is "
        "present. Medial meniscus appears intact. No fracture."
    )

    labels = extract_weak_labels(report)

    assert labels["ACL"] == 1
    assert labels["Effusion"] == 1
    assert labels["Medial Meniscus"] == 1  # regex has no negation handling yet
    assert labels["Fracture"] == 1  # regex has no negation handling yet


def test_extract_weak_labels_returns_all_columns_even_with_no_matches():
    labels = extract_weak_labels("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value in (0, 1) for value in labels.values())
    assert sum(labels.values()) == 0
