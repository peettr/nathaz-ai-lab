"""Approved deterministic selection of identical 0–6 h APCP GRIB messages."""
import hashlib
import numpy as np


def select_identical_apcp(messages):
    if not messages:
        raise ValueError('APCP_0-6h:messages=0')
    first = messages[0]
    digest = hashlib.sha256(first.tostring()).hexdigest()
    first_array = np.ma.asarray(first.values)
    first_mask = np.ma.getmaskarray(first_array)
    first_values = np.asarray(first_array.filled(np.nan))
    evidence = []
    for candidate in messages[1:]:
        other_digest = hashlib.sha256(candidate.tostring()).hexdigest()
        if other_digest == digest:
            method = 'same_grib_sha256'
        else:
            other_array = np.ma.asarray(candidate.values)
            other_mask = np.ma.getmaskarray(other_array)
            other_values = np.asarray(other_array.filled(np.nan))
            equal = (np.array_equal(first_mask, other_mask) and
                     np.array_equal(first_values, other_values, equal_nan=True))
            if not equal:
                raise ValueError('APCP_0-6h:nonidentical_duplicate')
            method = 'same_values_and_mask'
        evidence.append({'sha256': other_digest, 'equivalence': method})
    return first, {'dedup_identical': len(messages)-1,
                   'selected_sha256': digest, 'duplicates': evidence}
