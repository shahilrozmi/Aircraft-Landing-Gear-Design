sigma_mpa = 732.45
Sy_mpa = 505.0
Su_mpa = 572.0
target_ms_y = 0.1

sigma_yield_limit_mpa = Sy_mpa
sigma_target_ms10_mpa = Sy_mpa / (1.0 + target_ms_y)

reduction_to_yield_pct = 100.0 * (sigma_mpa - sigma_yield_limit_mpa) / sigma_mpa
reduction_to_ms10_pct = 100.0 * (sigma_mpa - sigma_target_ms10_mpa) / sigma_mpa

print(f"Current retained local peak: {sigma_mpa:.2f} MPa")
print(f"Stress reduction to reach Sy: {reduction_to_yield_pct:.2f} %")
print(f"Stress target for MS_y=+0.10: {sigma_target_ms10_mpa:.2f} MPa")
print(f"Stress reduction to reach MS_y=+0.10: {reduction_to_ms10_pct:.2f} %")
