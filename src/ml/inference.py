import torch
import pandas as pd

from typing import List
from datetime import datetime
from .dataset import get_time_diff, AKINormalizer, AKIDataset
from .model import AKIModel


def infer(
    model: AKIModel,
    normalizer: AKINormalizer,
    age: int,
    creatinine: List[int],
    dates: List[datetime],
) -> int:
    # Normalize inputs
    dates = get_time_diff(dates, time_unit="days")
    df = pd.DataFrame({"creatinine": [creatinine], "dates": [dates], "age": [age]})

    ds = AKIDataset(df=df, normalizer=normalizer, preprocess=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    model.to(device)

    age, levels, _ = ds[0]

    age = age.to(device)
    levels = levels.to(device)

    with torch.no_grad():
        output = model(levels, age)
        preds = (torch.sigmoid(output) > 0.5).int()

    return preds.cpu().numpy().item()
