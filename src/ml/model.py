import torch


class AKIModel(torch.nn.Module):
    def __init__(self, lstm_hidden_size=64, lstm_num_layers=2, fc_hidden_size=32):
        super(AKIModel, self).__init__()

        self.lstm = torch.nn.LSTM(
            input_size=2,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_num_layers,
            batch_first=True,
        )

        self.fc = torch.nn.Linear(lstm_hidden_size + 1, fc_hidden_size)
        self.output = torch.nn.Linear(fc_hidden_size, 1)

    def forward(self, levels, age):
        _, (h, _) = self.lstm(levels)
        h = h[-1]
        h = torch.cat([h, age], dim=-1)
        h = torch.relu(self.fc(h))
        h = self.output(h)

        return h
