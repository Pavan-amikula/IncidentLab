"""Expected service telemetry monitoring; missing data is not proof a service is down."""
from collections import defaultdict


def longest_gap(values):
    longest=current=0
    for present in values:
        current=0 if present else current+1
        longest=max(longest,current)
    return longest


def fit_inventory(rows):
    windows=sorted({r['window'] for r in rows});observed=defaultdict(set)
    for row in rows:
        if row['features'][17]<1:observed[row['service']].add(row['window'])
    expected={}
    for service,seen in observed.items():
        presence=[w in seen for w in windows]
        if sum(presence)/len(windows)>=.8:
            expected[service]=longest_gap(presence)+2
    return dict(expected_gap_minutes=expected,peer_coverage_required=.8,
                fitting='Designated healthy metric availability only; no fault labels')


class CoverageGuard:
    def __init__(self,bundle):
        self.expected=bundle['expected_gap_minutes']
        self.required=bundle['peer_coverage_required']
        self.gaps={service:0 for service in self.expected}
        self.last_end=None

    def step(self,end,observed):
        if end%60 or self.last_end is not None and end!=self.last_end+60:
            raise ValueError('Coverage windows must be consecutive epoch minutes')
        observed=set(observed);coverage=len(observed & self.expected.keys())/max(len(self.expected),1)
        if not self.expected or coverage<self.required:
            # Global collection gaps must not masquerade as many service outages.
            result=dict(state='insufficient_telemetry',peer_coverage=coverage,issues=[],
                action='Check collectors and inventory before attributing service failures')
            self.gaps={service:0 for service in self.expected}
        else:
            for service in self.expected:
                self.gaps[service]=0 if service in observed else self.gaps[service]+1
            issues=[dict(service=service,kind='expected_service_telemetry_gap',
                missing_minutes=self.gaps[service],threshold_minutes=threshold,
                evidence=f'No CPU/memory samples for {self.gaps[service]} consecutive minutes while {coverage:.0%} of expected peers are observed',
                action='Check service readiness, scrape target and deployment changes; absence alone does not prove root cause')
                for service,threshold in self.expected.items() if self.gaps[service]>=threshold]
            result=dict(state='coverage_warning' if issues else 'observed',peer_coverage=coverage,issues=issues)
        self.last_end=end
        return result
