"""Reporting precision shared by model reports and capture uncertainty (pure Python, no COM)."""

# Decimal places of model_report mass properties; capture uncertainty adds half of one step.
MASS_DECIMALS = {"volume_mm3": 2, "area_mm2": 2, "mass_kg": 5}
# Decimal places of model_report boxes and capture extents (mm).
LENGTH_DECIMALS = 3
# model_report lists at most this many features or mates with rebuild errors.
FEATURE_ERROR_LIMIT = 20
