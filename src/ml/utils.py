import numpy as np

from sklearn.metrics import precision_score, recall_score


def get_metrics(y_true, y_pred):
    fp = int(np.sum(np.logical_and(y_true == 0, y_pred == 1)))
    tp = int(np.sum(np.logical_and(y_true == 1, y_pred == 1)))
    fn = int(np.sum(np.logical_and(y_true == 1, y_pred == 0)))
    tn = int(np.sum(np.logical_and(y_true == 0, y_pred == 0)))

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f3 = (1 + 3**2) * (precision * recall) / (3**2 * precision + recall + 1e-8)

    metrics = {
        "fp": fp,
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f3": f3,
    }

    return metrics
