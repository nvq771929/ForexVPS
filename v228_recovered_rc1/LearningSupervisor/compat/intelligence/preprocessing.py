"""Training-only scaling with explicit binary/signed-category handling."""
def binary_indices(names):
    exact={'support_available','resistance_available','structure_up','structure_down','candidate_present',
           'candidate_direction','candidate_sr1','candidate_tp1','candidate_br1','reward_available'}
    return [i for i,n in enumerate(names) if n in exact or n.startswith('regime_')]
