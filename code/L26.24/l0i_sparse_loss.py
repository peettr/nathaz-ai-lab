"""Eq. (7) Hutchinson m=1 loss; indexed sparse matvec avoids dense sparse-autograd gradients."""
import torch
from apps.data import graph_to_matrix


def indexed_spmv(matrix, vector):
    coo = matrix.coalesce()
    rows, cols = coo.indices().unbind(0)
    result = torch.zeros((coo.shape[0], vector.shape[1]), dtype=vector.dtype, device=vector.device)
    return result.index_add(0, rows, coo.values().unsqueeze(1) * vector[cols])


def hutchinson_eq7(output, data):
    A, _ = graph_to_matrix(data)
    L = output.coalesce()
    w = torch.randn((A.shape[0], 1), dtype=L.dtype, device=L.device)
    residual = indexed_spmv(L, indexed_spmv(L.transpose(0, 1), w)) - indexed_spmv(A, w)
    # Repo sketched_loss returns the norm, not its square; preserve training gradients.
    # Its square is exactly the m=1 estimator in paper Eq. (7).
    return torch.linalg.vector_norm(residual, ord=2)
