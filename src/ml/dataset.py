import pandas as pd
import numpy as np
import torch

from torch.utils.data import Dataset
from torch.nn.utils.rnn import pack_padded_sequence, pad_sequence
from sklearn.preprocessing import MinMaxScaler
from src.utils import collapse_columns


def get_time_diff(dates, time_unit="days"):
    result = np.array(
        [0] + [(dates[i] - dates[i - 1]).total_seconds() for i in range(1, len(dates))]
    )
    if time_unit == "seconds":
        return result
    elif time_unit == "hours":
        return result / 3600
    elif time_unit == "days":
        return result / 86400


def preprocess_data(df):
    if "sex" in df.columns:
        df = df.drop(columns=["sex"])

    level_cols = [col for col in df.columns if "result" in col]
    date_cols = [col for col in df.columns if "date" in col]

    # Collapse time series into a single column
    df = collapse_columns(df, level_cols, "creatinine")
    df = collapse_columns(df, date_cols, "dates")

    # Map dates to intervals between measurements
    df["dates"] = df["dates"].apply(lambda x: [pd.to_datetime(d) for d in x])
    df["dates"] = df["dates"].apply(lambda x: get_time_diff(x, time_unit="days"))

    return df


class AKIDataset(Dataset):
    def __init__(self, df=None, file_name=None, normalizer=None, preprocess=True):
        # Load data
        assert df is not None or file_name is not None, (
            "Either df or file_name must be provided"
        )

        if df is not None:
            self._df = df
        else:
            self._df = pd.read_csv(file_name)

        # Preprocess data
        if preprocess:
            self._df = preprocess_data(self._df)

        # Normalizers
        self._normalizer = normalizer
        if self._normalizer is None:
            self._normalizer = AKINormalizer()
            self._normalizer.fit(self._df)

        # Normalize data
        self._df = self._normalizer.transform_df(self._df)

        self.age = torch.tensor(self._df["age"].tolist(), dtype=torch.float32).reshape(
            -1, 1
        )
        self.levels = [
            torch.tensor(x, dtype=torch.float32)
            for x in self._df["creatinine"].tolist()
        ]
        self.dates = [
            torch.tensor(x, dtype=torch.float32) for x in self._df["dates"].tolist()
        ]

        if "aki" in self._df.columns:
            self.y = torch.tensor(
                (self._df["aki"] == "y").astype(int).tolist(), dtype=torch.int64
            ).reshape(-1, 1)
        else:
            mock_y = [0] * len(self._df)
            self.y = torch.tensor(mock_y, dtype=torch.int64).reshape(-1, 1)

    @property
    def normalizer(self):
        return self._normalizer

    def __getitem__(self, idx):
        return (
            self.age[idx],
            torch.stack([self.levels[idx], self.dates[idx]], dim=-1),
            self.y[idx],
        )

    def __len__(self):
        return len(self._df)


class AKINormalizer:
    def __init__(self):
        self.level_normalizer = MinMaxScaler()
        self.date_normalizer = MinMaxScaler()
        self.age_normalizer = MinMaxScaler()

    def fit(self, df):
        # Fit normalizers
        levels = np.concatenate(df["creatinine"].tolist())
        self.level_normalizer.fit(levels.reshape(-1, 1))

        dates = np.concatenate(df["dates"].tolist())
        self.date_normalizer.fit(dates.reshape(-1, 1))

        ages = df["age"].tolist()
        self.age_normalizer.fit(np.array(ages).reshape(-1, 1))

    def transform_df(self, df):
        df["creatinine"] = df["creatinine"].apply(
            lambda x: self.level_normalizer.transform(
                np.array(x).reshape(-1, 1)
            ).reshape(-1)
        )

        df["dates"] = df["dates"].apply(
            lambda x: self.date_normalizer.transform(
                np.array(x).reshape(-1, 1)
            ).reshape(-1)
        )

        ages = df["age"].tolist()
        df["age"] = self.age_normalizer.transform(
            np.array(ages).reshape(-1, 1)
        ).reshape(-1)
        return df

    def transform(self, age, creatinine, dates):
        creatinine = self.level_normalizer.transform(
            np.array(creatinine).reshape(-1, 1)
        ).reshape(-1)
        dates = self.date_normalizer.transform(np.array(dates).reshape(-1, 1)).reshape(
            -1
        )
        age = self.age_normalizer.transform(np.array(age).reshape(-1, 1)).reshape(-1)
        return age, creatinine, dates

    def save(self, path):
        torch.save(
            {
                "level_normalizer": self.level_normalizer,
                "date_normalizer": self.date_normalizer,
                "age_normalizer": self.age_normalizer,
            },
            path,
        )

    @staticmethod
    def load(path):
        normalizers = torch.load(path)

        obj = AKINormalizer()

        obj.level_normalizer = normalizers["level_normalizer"]
        obj.date_normalizer = normalizers["date_normalizer"]
        obj.age_normalizer = normalizers["age_normalizer"]

        return obj


def aki_collate_fn(batch):
    ages, levels, y = zip(*batch)

    # Compute lengths
    lengths = torch.tensor([len(x) for x in levels])

    # Sort by length
    indices = torch.argsort(lengths, descending=True)
    lengths = lengths[indices]
    ages = torch.stack(ages)[indices]
    levels = [levels[i] for i in indices]
    y = torch.stack(y)[indices]

    # Pad sequences
    levels = pad_sequence(levels, batch_first=True)

    # Pack padded sequences
    levels = pack_padded_sequence(
        levels, lengths, batch_first=True, enforce_sorted=False
    )

    return ages, levels, y
