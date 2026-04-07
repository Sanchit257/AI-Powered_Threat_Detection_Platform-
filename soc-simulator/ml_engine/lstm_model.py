"""LSTM sequence autoencoder for temporal anomaly scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from features import vectorize_batch

SEQ_LEN = 10
FEAT_DIM = 8
HIDDEN = 32


class LSTMAutoencoder(nn.Module):
    """Encodes sequence -> latent from last hidden state, decodes to full sequence."""

    def __init__(self, input_dim: int = FEAT_DIM, hidden_dim: int = HIDDEN, seq_len: int = SEQ_LEN):
        super().__init__()
        self.seq_len = seq_len
        self.encoder = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, feat)
        _, (h, _) = self.encoder(x)
        h = h.squeeze(0)  # (batch, hidden)
        dec_in = h.unsqueeze(1).expand(-1, self.seq_len, -1)
        dec_out, _ = self.decoder(dec_in)
        return self.fc(dec_out)


class LSTMDetector:
    def __init__(self, device: str | None = None) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = LSTMAutoencoder().to(self.device)
        self._mse_cap: float = 1.0

    def _tensor(self, seq: np.ndarray) -> torch.Tensor:
        t = torch.tensor(seq, dtype=torch.float32, device=self.device)
        if t.dim() == 2:
            t = t.unsqueeze(0)
        return t

    def train(self, sequences: Sequence[Sequence[Mapping[str, Any]]], epochs: int = 15, lr: float = 1e-3) -> None:
        """sequences: list of length-10 log dict lists."""
        if not sequences:
            return
        X = np.stack([vectorize_batch(list(s)) for s in sequences], axis=0)
        if X.shape[0] == 0:
            return
        t = self._tensor(X)
        opt = optim.Adam(self.model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()
        self.model.train()
        for _ in range(epochs):
            opt.zero_grad()
            recon = self.model(t)
            loss = loss_fn(recon, t)
            loss.backward()
            opt.step()
        self.model.eval()
        with torch.no_grad():
            recon = self.model(t)
            mse = torch.mean((recon - t) ** 2, dim=(1, 2)).cpu().numpy()
        self._mse_cap = float(np.percentile(mse, 95)) + 1e-6
        if self._mse_cap < 1e-5:
            self._mse_cap = 1e-5

    def score(self, sequence_of_10_logs: Sequence[Mapping[str, Any]]) -> float:
        """Reconstruction error mapped to 0-10."""
        if len(sequence_of_10_logs) != SEQ_LEN:
            raise ValueError(f"need {SEQ_LEN} logs, got {len(sequence_of_10_logs)}")
        X = vectorize_batch(list(sequence_of_10_logs))
        t = self._tensor(X)
        self.model.eval()
        with torch.no_grad():
            recon = self.model(t)
            mse = float(torch.mean((recon - t) ** 2).item())
        cap = max(self._mse_cap, 1e-6)
        return float(min(10.0, 10.0 * mse / cap))

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state": self.model.state_dict(),
                "mse_cap": self._mse_cap,
            },
            path,
        )

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device)
        self.model.load_state_dict(ckpt["state"])
        self._mse_cap = float(ckpt.get("mse_cap", 1.0))
        self.model.eval()
