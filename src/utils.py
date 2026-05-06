import pandas as pd


def collapse_columns(df, cols, new_col):
    cdf = df.copy()
    cdf[new_col] = cdf.apply(
        lambda row: [row[col] for col in cols if not pd.isna(row[col])], axis=1
    )
    cdf.drop(columns=cols, inplace=True)
    return cdf
