"""Три помощника из timm.layers, которые нужны swin_v1.py (правка проекта: timm не тянем)."""
import torch
import torch.nn as nn


def to_2tuple(x):
    return tuple(x) if isinstance(x, (tuple, list)) else (x, x)


def trunc_normal_(tensor, mean=0., std=1., a=-2., b=2.):
    return nn.init.trunc_normal_(tensor, mean=mean, std=std, a=a, b=b)


class DropPath(nn.Module):
    """Стохастическая глубина: при выводе маски (eval) — тождество, как в timm."""

    def __init__(self, drop_prob=0.):
        super().__init__()
        self.drop_prob = drop_prob

    def forward(self, x):
        if self.drop_prob == 0. or not self.training:
            return x
        keep = 1 - self.drop_prob
        mask = x.new_empty((x.shape[0],) + (1,) * (x.ndim - 1)).bernoulli_(keep)
        return x * mask / keep
