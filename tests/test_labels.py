from knee_mri.labels import (
    LABEL_COLUMNS,
    LabelResolution,
    MentionDiagnostic,
    _resolution_signature,
    _resolve_value,
    _resolve_weak_labels,
    extract_weak_labels,
    extract_weak_labels_naive,
)


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


# -- extract_weak_labels_naive: frozen baseline, unchanged behavior --


def test_extract_weak_labels_naive_detects_multiple_findings():
    report = (
        "There is a complete tear of the ACL. Moderate joint effusion is "
        "present. Medial meniscus appears intact. No fracture."
    )

    labels = extract_weak_labels_naive(report)

    assert labels["ACL"] == 1
    assert labels["Effusion"] == 1
    assert labels["Medial Meniscus"] == 1  # regex has no negation handling
    assert labels["Fracture"] == 1  # regex has no negation handling


def test_extract_weak_labels_naive_returns_all_columns_even_with_no_matches():
    labels = extract_weak_labels_naive("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value in (0, 1) for value in labels.values())
    assert sum(labels.values()) == 0


# -- extract_weak_labels: new assertion-aware behavior --


def test_extract_weak_labels_unqualified_mention_is_positive():
    labels = extract_weak_labels("There is a complete tear of the ACL.")

    assert labels["ACL"] == 1


def test_extract_weak_labels_negated_mention_is_negative():
    labels = extract_weak_labels("No fracture is seen.")

    assert labels["Fracture"] == 0


def test_extract_weak_labels_post_match_cue_heading_colon():
    # The exact "ACL: intact" case round-6 review found broken by naive
    # ':'-splitting -- the cue follows the keyword, in the same "clause"
    # only because ':' is not a clause boundary.
    labels = extract_weak_labels("ACL: intact.")

    assert labels["ACL"] == 0


def test_extract_weak_labels_uncertain_cue_abstains():
    labels = extract_weak_labels("Rule out fracture in this region.")

    assert labels["Fracture"] is None


def test_extract_weak_labels_substring_trap_does_not_trigger_negation():
    # "notable" must never match the "no" cue -- no word boundary
    # between "no" and "table" inside "notable".
    labels = extract_weak_labels("Effusion is notable in the joint.")

    assert labels["Effusion"] == 1


def test_extract_weak_labels_cue_does_not_leak_across_clause_boundary():
    labels = extract_weak_labels("No fracture is seen. ACL is torn.")

    assert labels["Fracture"] == 0
    assert labels["ACL"] == 1


def test_extract_weak_labels_repeated_concordant_mentions_stay_positive():
    labels = extract_weak_labels(
        "The ACL is torn. Findings of ACL tear are confirmed."
    )

    assert labels["ACL"] == 1


def test_extract_weak_labels_abstains_on_all_labels_with_no_mentions():
    labels = extract_weak_labels("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value is None for value in labels.values())


# -- _resolve_weak_labels: internal resolver, full LabelResolution detail --


def test_resolve_weak_labels_unqualified_mention():
    resolution = _resolve_weak_labels("There is a complete tear of the ACL.")["ACL"]

    assert resolution == LabelResolution(
        value=1, mentions=(MentionDiagnostic(kind="unqualified", clause_index=0),)
    )


def test_resolve_weak_labels_negated_mention():
    resolution = _resolve_weak_labels("No fracture is seen.")["Fracture"]

    assert resolution == LabelResolution(
        value=0,
        mentions=(MentionDiagnostic(kind="qualified_negation", clause_index=0),),
    )


def test_resolve_weak_labels_normal_assertion_mention():
    resolution = _resolve_weak_labels("ACL: intact.")["ACL"]

    assert resolution == LabelResolution(
        value=0,
        mentions=(MentionDiagnostic(kind="qualified_normal_assertion", clause_index=0),),
    )


def test_resolve_weak_labels_uncertain_mention():
    resolution = _resolve_weak_labels("Rule out fracture in this region.")["Fracture"]

    assert resolution == LabelResolution(
        value=None,
        mentions=(MentionDiagnostic(kind="qualified_uncertain", clause_index=0),),
    )


def test_resolve_weak_labels_no_mention():
    resolution = _resolve_weak_labels("Normal knee MRI, no significant findings.")["ACL"]

    assert resolution == LabelResolution(value=None, mentions=())


# -- _resolution_signature / _resolve_value: the invariant the error
# taxonomy in the evaluation notebook depends on --


def test_resolution_signature_and_value_are_consistent_for_every_signature():
    """For every one of the six resolution_signature values, confirm the
    value is consistent with exactly one direction of error:
    unqualified_only is the only signature that can ever produce
    value=1 (and therefore a false positive); every other signature
    produces 0 or None (and therefore, when wrong, only a false
    negative). A future change to the resolution order must not
    silently invalidate this without breaking this test."""
    no_mention: tuple[MentionDiagnostic, ...] = ()
    only_unqualified = (MentionDiagnostic(kind="unqualified", clause_index=0),)
    only_negation = (MentionDiagnostic(kind="qualified_negation", clause_index=0),)
    only_normal = (MentionDiagnostic(kind="qualified_normal_assertion", clause_index=0),)
    only_uncertain = (MentionDiagnostic(kind="qualified_uncertain", clause_index=0),)
    mixed = (
        MentionDiagnostic(kind="unqualified", clause_index=0),
        MentionDiagnostic(kind="qualified_negation", clause_index=1),
    )

    cases = [
        (no_mention, "no_mention"),
        (only_unqualified, "unqualified_only"),
        (only_negation, "negation_qualified"),
        (only_normal, "normal_qualified"),
        (only_uncertain, "uncertain_qualified"),
        (mixed, "mixed_qualification"),
    ]

    for mentions, expected_signature in cases:
        signature = _resolution_signature(mentions)
        value = _resolve_value(mentions)

        assert signature == expected_signature
        if signature == "unqualified_only":
            assert value == 1
        else:
            assert value != 1
