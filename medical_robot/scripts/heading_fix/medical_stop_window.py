"""Read-only strict consecutive stop evidence; never changes odometry."""
from __future__ import division
import math


class StopWindow(object):
    def __init__(self):
        self.rows = []
        self.last = None
        self.resets = []

    def feed(self, row):
        reason = None
        if not all(not math.isnan(row[k]) and not math.isinf(row[k])
                   for k in ('t', 'stamp', 'vx', 'vy', 'wz')):
            reason = 'nonfinite'
        elif max(abs(row['vx']), abs(row['vy']), abs(row['wz'])) > .002:
            reason = 'nonstationary'
        elif self.last is not None and (row['t'] <= self.last['t'] or
              row['stamp'] <= self.last['stamp'] or
              row['t'] - self.last['t'] > .2 or
              row['stamp'] - self.last['stamp'] > .2):
            reason = 'gap_or_nonmonotonic'
        if reason:
            self.rows = []
            self.resets.append(dict(t=row['t'], reason=reason))
        else:
            self.rows.append(dict(row))
            while len(self.rows) > 1 and row['t'] - self.rows[1]['t'] >= 4:
                self.rows.pop(0)
        self.last = dict(row)

    def evidence(self, now):
        age = now - self.last['t'] if self.last else None
        span = self.rows[-1]['t'] - self.rows[0]['t'] if self.rows else 0
        good = (len(self.rows) >= 100 and span >= 4 and
                age is not None and 0 <= age <= .2)
        return dict(passed=good, samples=len(self.rows), span_seconds=span,
                    age_seconds=age, reset_events=list(self.resets),
                    threshold=.002, max_gap=.2, required_span=4,
                    note='Feedback evidence only; physical observation still required')
