"""Regression evaluation utilities.

* :func:`compute_metrics` — MAE, RMSE, MedianAE, R².
* :func:`time_based_split` — chronological train/validation split to avoid
  data leakage (future cases should not inform past-case predictions).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Return a dict of regression quality metrics.

    Parameters
    ----------
    y_true:
        Ground-truth target values (duration in days).
    y_pred:
        Model predictions.

    Returns
    -------
    dict with keys: ``mae``, ``rmse``, ``median_ae``, ``r2``.
    """
    from sklearn.metrics import (
        mean_absolute_error,
        mean_squared_error,
        median_absolute_error,
        r2_score,
    )

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    medae = float(median_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "median_ae": round(medae, 2),
        "r2": round(r2, 4),
    }


def time_based_split(
    df: pd.DataFrame,
    date_col: str = "filing_date",
    train_fraction: float = 0.8,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split *df* chronologically so that the training set contains older cases.

    Parameters
    ----------
    df:
        DataFrame that must include *date_col*.
    date_col:
        Column used for ordering (defaults to ``filing_date``).
    train_fraction:
        Fraction of rows assigned to the training split (default 0.8).

    Returns
    -------
    (train_df, val_df)
        Two non-overlapping DataFrames.  All training rows have an earlier
        *date_col* value than all validation rows.
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    cutoff = int(len(df_sorted) * train_fraction)
    return df_sorted.iloc[:cutoff].copy(), df_sorted.iloc[cutoff:].copy()
