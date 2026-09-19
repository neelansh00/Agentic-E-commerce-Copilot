"""Allowlisted arithmetic over complete ordinal histograms; never eval/exec."""
def compare_review_histograms(result):
    if result.truncated:
        raise ValueError('Analysis requires a complete result, not a preview.')
    if set(result.columns) != {'is_late', 'review_score', 'n'}:
        raise ValueError('Expected binary-group review histogram columns.')
    counts = {0: {}, 1: {}}
    for row in result.rows:
        group, score, n = row['is_late'], row['review_score'], row['n']
        if any(type(v) is not int for v in (group, score, n)) or group not in counts or not 1 <= score <= 5 or n <= 0:
            raise ValueError('Invalid histogram group, ordinal score or count.')
        if score in counts[group]:
            raise ValueError('Duplicate histogram cell.')
        counts[group][score] = n
    totals = {g: sum(c.values()) for g, c in counts.items()}
    if not all(totals.values()):
        raise ValueError('Both late and on-time groups need reviewed eligible orders.')
    means = {g: sum(s*n for s, n in c.items()) / totals[g] for g, c in counts.items()}
    pairs = totals[0] * totals[1]
    lower = sum(n*m for s, n in counts[1].items() for t, m in counts[0].items() if s < t) / pairs
    equal = sum(n*counts[0].get(s, 0) for s, n in counts[1].items()) / pairs
    return dict(on_time_orders=totals[0], late_orders=totals[1],
                on_time_mean=means[0], late_mean=means[1],
                mean_difference_late_minus_on_time=means[1]-means[0],
                probability_late_score_lower=lower, probability_equal_score=equal,
                probability_late_score_higher=max(0.0, 1-lower-equal))


def describe_comparison(values):
    return [
        f"Reviewed eligible orders: {values['late_orders']:,} late; {values['on_time_orders']:,} on time.",
        f"Mean review score: late {values['late_mean']:.3f}; on time {values['on_time_mean']:.3f} (one-to-five scale).",
        f"Late minus on-time mean: {values['mean_difference_late_minus_on_time']:.3f} score points.",
        f"Across all cross-group pairs, the late order has a lower score in {100*values['probability_late_score_lower']:.2f}% and an equal score in {100*values['probability_equal_score']:.2f}% of pairs.",
    ]
