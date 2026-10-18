"""
Lu et al. 2025 baseline UNet - with circular padding.
Only change: Conv2d padding uses circular mode instead of zero (default).
"""
from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F


class CircularConvBlock(nn.Module):
    """Two 3x3 conv-BN-ReLU layers with circular padding."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=0, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=0, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Circular pad: (left, right, top, bottom)
        x = F.pad(x, [1, 1, 1, 1], mode='circular')
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.pad(x, [1, 1, 1, 1], mode='circular')
        x = F.relu(self.bn2(self.conv2(x)))
        return x


class UNetLuCircular(nn.Module):
    """
    Five-level UNet with circular padding.
    """

    def __init__(self, n_c: int = 16) -> None:
        super().__init__()
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        self.enc1 = CircularConvBlock(1, n_c)
        self.enc2 = CircularConvBlock(n_c, 2 * n_c)
        self.enc3 = CircularConvBlock(2 * n_c, 4 * n_c)
        self.enc4 = CircularConvBlock(4 * n_c, 8 * n_c)
        self.bottleneck = CircularConvBlock(8 * n_c, 16 * n_c)

        self.up4 = nn.ConvTranspose2d(16 * n_c, 8 * n_c, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.dec4 = CircularConvBlock(16 * n_c, 8 * n_c)
        self.up3 = nn.ConvTranspose2d(8 * n_c, 4 * n_c, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.dec3 = CircularConvBlock(8 * n_c, 4 * n_c)
        self.up2 = nn.ConvTranspose2d(4 * n_c, 2 * n_c, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.dec2 = CircularConvBlock(4 * n_c, 2 * n_c)
        self.up1 = nn.ConvTranspose2d(2 * n_c, n_c, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.dec1 = CircularConvBlock(2 * n_c, n_c)

        self.out_conv = nn.Sequential(
            nn.Conv2d(n_c, 1, kernel_size=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))

        d4 = self.dec4(self._pad_cat(self.up4(b), e4))
        d3 = self.dec3(self._pad_cat(self.up3(d4), e3))
        d2 = self.dec2(self._pad_cat(self.up2(d3), e2))
        d1 = self.dec1(self._pad_cat(self.up1(d2), e1))
        return self.out_conv(d1)

    @staticmethod
    def _pad_cat(x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        diff_h = skip.size(2) - x.size(2)
        diff_w = skip.size(3) - x.size(3)
        if diff_h != 0 or diff_w != 0:
            x = F.pad(x, [diff_w // 2, diff_w - diff_w // 2, diff_h // 2, diff_h - diff_h // 2])
        return torch.cat([x, skip], dim=1)


__all__ = ['UNetLuCircular']
