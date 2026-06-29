"""Optional RDL/GNN backend (relbench + PyTorch Geometric).

A heterogeneous, temporal Graph Neural Network over the relational graph — the Phase-2
"real RDL" path. It assembles relbench's reference building blocks (HeteroEncoder +
HeteroTemporalEncoder + HeteroGraphSAGE) into a node-prediction model and trains it with
time-aware neighbor sampling, so it can beat the cheap DFS baseline on tasks where the
relational/temporal structure matters.

HEAVY + optional. Needs the ``eval`` extra (torch, relbench, pytorch-frame) **plus** PyG and a
neighbor-sampling backend (``torch-sparse`` / ``pyg-lib``). Kept out of the core; import only
through ``realpath.eval --gnn``. Text columns are dropped to avoid a text-embedder dependency.
"""
from __future__ import annotations

from ._io import sprint


def _drop_text_stypes(col_to_stype: dict) -> dict:
    """Drop text_embedded columns so make_pkey_fkey_graph needs no text embedder."""
    return {
        tbl: {c: s for c, s in cols.items() if str(s) != "text_embedded"}
        for tbl, cols in col_to_stype.items()
    }


def _has_pyg_lib() -> bool:
    import importlib.util

    return importlib.util.find_spec("pyg_lib") is not None


def run_gnn_task(
    dataset_name: str,
    task_name: str,
    epochs: int = 10,
    channels: int = 128,
    num_neighbors=(64, 64),
    batch_size: int = 512,
    lr: float = 5e-3,
    seed: int = 42,
    temporal: bool = True,
) -> dict:
    import numpy as np
    import torch
    from relbench.datasets import get_dataset
    from relbench.modeling.graph import get_node_train_table_input, make_pkey_fkey_graph
    from relbench.modeling.nn import HeteroEncoder, HeteroGraphSAGE, HeteroTemporalEncoder
    from relbench.modeling.utils import get_stype_proposal
    from relbench.tasks import get_task
    from torch_geometric.loader import NeighborLoader
    from torch_geometric.seed import seed_everything

    from .engine import _metrics

    seed_everything(seed)
    dataset = get_dataset(dataset_name, download=True)
    task = get_task(dataset_name, task_name, download=True)
    db = dataset.get_db()
    col_to_stype = _drop_text_stypes(get_stype_proposal(db))
    data, col_stats = make_pkey_fkey_graph(db, col_to_stype, text_embedder_cfg=None, cache_dir=None)

    is_reg = "regress" in str(getattr(task, "task_type", "")).lower()
    entity_table = task.entity_table
    num_layers = len(num_neighbors)

    # Time-aware (disjoint) sampling needs pyg-lib, which has no Windows build. Without it we
    # fall back to NON-temporal sampling — fast to verify the model, but NOT leakage-safe, so
    # the metric is not a fair benchmark vs the (leakage-safe) DFS baseline.
    if temporal and not _has_pyg_lib():
        temporal = False
        sprint("[realpath] pyg-lib bulunamadi -> NON-TEMPORAL sampling (LEAKY; sadece kod "
               "dogrulamasi, adil benchmark DEGIL). Adil temporal egitim icin pyg-lib (Linux) gerekir.")

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = HeteroEncoder(
                channels,
                {nt: data[nt].tf.col_names_dict for nt in data.node_types},
                col_stats,
            )
            self.temporal = HeteroTemporalEncoder(
                [nt for nt in data.node_types if "time" in data[nt]], channels
            )
            self.gnn = HeteroGraphSAGE(
                data.node_types, data.edge_types, channels, num_layers=num_layers
            )
            self.head = torch.nn.Linear(channels, 1)

        def forward(self, batch):
            ent = batch[entity_table]
            n_seed = getattr(ent, "batch_size", None) or int(ent.y.size(0))
            x = self.encoder(batch.tf_dict)
            if temporal:  # temporal encoder needs disjoint sampling's seed_time + batch_dict
                for nt, rel in self.temporal(
                    ent.seed_time, batch.time_dict, batch.batch_dict
                ).items():
                    x[nt] = x[nt] + rel
            x = self.gnn(x, batch.edge_index_dict)
            return self.head(x[entity_table][:n_seed]).squeeze(-1)

    model = Model()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss() if is_reg else torch.nn.BCEWithLogitsLoss()

    def loader(split: str, shuffle: bool):
        ti = get_node_train_table_input(task.get_table(split), task)
        kw = dict(input_nodes=ti.nodes, transform=ti.transform,
                  batch_size=batch_size, shuffle=shuffle, num_workers=0)
        if temporal:
            kw.update(time_attr="time", input_time=ti.time)
        return NeighborLoader(data, num_neighbors=list(num_neighbors), **kw)

    train_loader = loader("train", True)
    for ep in range(epochs):
        model.train()
        tot = n = 0
        for batch in train_loader:
            opt.zero_grad()
            pred = model(batch)
            y = batch[entity_table].y.float()
            loss = loss_fn(pred, y)
            loss.backward()
            opt.step()
            tot += float(loss) * y.size(0)
            n += int(y.size(0))
        sprint(f"  epoch {ep + 1}/{epochs}  loss={tot / max(n, 1):.4f}")

    @torch.no_grad()
    def predict(split: str):
        ld = loader(split, False)
        model.eval()
        ps, ys = [], []
        for batch in ld:
            p = model(batch)
            if not is_reg:
                p = torch.sigmoid(p)
            ps.append(p.numpy())
            ys.append(batch[entity_table].y.numpy())
        return np.concatenate(ps), np.concatenate(ys)

    # test labels are masked on the leaderboard split -> evaluate on val
    yhat, y = predict("val")
    metrics = _metrics("regression" if is_reg else "classification", y, yhat)
    kind = "regression" if is_reg else "classification"
    sprint(f"\nGNN {dataset_name}/{task_name} [{kind}]  -> {metrics}\n")
    return metrics
