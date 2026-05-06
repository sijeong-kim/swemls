import torch
import numpy as np

from torch.utils.data import DataLoader
from tqdm import tqdm
from .utils import get_metrics


def train(
    model,
    train_dataset,
    val_dataset,
    collate_fn,
    num_epochs=10,
    batch_size=32,
    lr=1e-3,
    early_stopping_patience=3,
    save_best=True,
    checkpoint_dir="checkpoints",
):
    # Device setup
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    # Class weights for imbalanced dataset
    train_y = train_dataset.y.squeeze().numpy()
    num_pos = np.sum(train_y)
    num_neg = len(train_y) - num_pos
    pos_weight = num_neg / num_pos

    # Loss function
    criterion = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pos_weight).to(device)
    )
    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    # Scheduler
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=2, verbose=True
    )

    # Data loaders
    train_dl = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn
    )
    val_dl = DataLoader(val_dataset, batch_size=batch_size, collate_fn=collate_fn)

    # Training loop
    best_val_loss = np.inf
    best_epoch = 0

    # Training history
    history = []

    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0

        # Progress bar
        train_pbar = tqdm(
            train_dl, desc=f"Epoch {epoch + 1}/{num_epochs}", unit="batch"
        )

        # Training loop
        for batch in train_pbar:
            age, levels, y = [x.to(device) for x in batch]

            optimizer.zero_grad()

            output = model(levels, age)
            loss = criterion(output, y.float())
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_dl)
        train_pbar.set_postfix(train_loss=train_loss)

        # Validation loop
        model.eval()
        val_loss = 0.0
        val_y_true, val_y_pred = [], []

        for batch in val_dl:
            age, levels, y = [x.to(device) for x in batch]

            output = model(levels, age)
            loss = criterion(output, y.float())

            val_loss += loss.item()
            preds = (torch.sigmoid(output) > 0.5).int()
            val_y_true.extend(y.tolist())
            val_y_pred.extend(preds.tolist())

        val_loss /= len(val_dl)

        # Save metrics
        metrics = get_metrics(np.array(val_y_true), np.array(val_y_pred))
        metrics["train_loss"] = train_loss
        metrics["val_loss"] = val_loss
        history.append(metrics)

        print(f"Epoch {epoch + 1}/{num_epochs}: {metrics}")

        # Update learning rate
        scheduler.step(val_loss)

        # Save model
        if save_best and val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            torch.save(model.state_dict(), f"{checkpoint_dir}/best_model.pth")
            print("Saved best model")

        elif not save_best:
            torch.save(model.state_dict(), f"{checkpoint_dir}/epoch_{epoch + 1}.pth")
            print(f"Saved model checkpoint at epoch {epoch + 1}")

        # Early stopping
        if epoch - best_epoch >= early_stopping_patience:
            print(f"Stopping early at epoch {epoch + 1}")
            break

    print("Training complete")
    return history


def evaluate(model, dataset, collate_fn):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    dl = DataLoader(dataset, batch_size=32, collate_fn=collate_fn)

    y_true, y_pred = [], []

    for batch in dl:
        age, levels, y = [x.to(device) for x in batch]

        output = model(levels, age)
        preds = (torch.sigmoid(output) > 0.5).int()

        y_true.extend(y.tolist())
        y_pred.extend(preds.tolist())

    return get_metrics(np.array(y_true), np.array(y_pred))
