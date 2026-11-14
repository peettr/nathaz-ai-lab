"""M4 causal-information checks, shared by training and frozen scorer.

No holdout observations are read by this module. The scorer must call
check_cutoffs on EVERY row before any aggregate or plot.
"""
from datetime import datetime, timedelta, timezone


def utc(value):
    if isinstance(value, datetime):
        t = value
    else:
        t = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError(f'Naive UTC timestamp prohibited: {value!r}')
    return t.astimezone(timezone.utc)


def check_cutoffs(rows, delay_hours):
    """Raise on future information or unavailable initialization, even one row."""
    n = 0
    for n, row in enumerate(rows, 1):
        issue = utc(row['issue_utc'])
        cutoff = utc(row['info_cutoff_utc'])
        init = utc(row['init_utc'])
        if cutoff > issue:
            raise ValueError(f'row {n}: info_cutoff_utc > issue_utc')
        if init + timedelta(hours=delay_hours) > issue:
            raise ValueError(f'row {n}: init_utc + delay > issue_utc')
        valid = utc(row['valid_end_utc'])
        if valid <= issue or int(row['lead_min']) != (valid - issue).total_seconds() / 60:
            raise ValueError(f'row {n}: invalid lead/valid_end_utc')
    return n


if __name__ == '__main__':
    base = dict(issue_utc='2023-01-01T04:00:00Z', init_utc='2023-01-01T00:00:00Z', info_cutoff_utc='2023-01-01T04:00:00Z', valid_end_utc='2023-01-01T04:10:00Z', lead_min=10)
    assert check_cutoffs([base], 4) == 1
    for field, value in [('info_cutoff_utc', '2023-01-01T04:01:00Z'), ('init_utc', '2023-01-01T06:00:00Z'), ('lead_min', 20)]:
        bad = {**base, field: value}
        try:
            check_cutoffs([base, bad], 4)
        except ValueError:
            continue
        raise AssertionError(f'guard did not catch {field}')
    print('causality checks passed')
