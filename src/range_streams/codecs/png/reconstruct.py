from __future__ import annotations

__all__ = ["PaethPredictor"]


def reconstruct_idat(
    idat_bytes: bytes, channels: int, height: int, width: int
) -> list[int]:  # pragma: no cover
    """
    Parse a list of (zlib-decompressed) bytes into a flat list of integers (the pixel
    values), validating that the resulting list is the correct length.

    Adapted from demo implementation at https://pyokagan.name/blog/2019-10-14-png/

    Args:
      idat_bytes : The zlib-decompressed bytes from one or more IDAT chunks
      channels   : The number of channels in the image (e.g. RGBA has 4)
      height     : The height of the image (i.e. number of scanlines/rows)
      width      : The width of the image (i.e. number of columns)
    """
    recon_vals: list[int] = []
    stride = width * channels
    expected_len = stride * height
    i = 0
    for r in range(height):
        filter_type = idat_bytes[i]  # first byte of scanline is filter type
        i += 1
        for c in range(stride):
            x = idat_bytes[i]
            i += 1
            if not (0 <= filter_type <= 4):
                raise ValueError(f"Unknown filter type: {filter_type}")
            # Calculate the filter component(s) if/as needed for each type
            if filter_type in (1, 3, 4):
                a = recon_vals[r * stride + c - channels] if c >= channels else 0
            if filter_type > 1:
                b = recon_vals[(r - 1) * stride + c] if r > 0 else 0
            elif filter_type == 4:  # Paeth
                c = (
                    recon_vals[(r - 1) * stride + c - channels]
                    if r > 0 and c >= channels
                    else 0
                )
            # Use the calculated filter component(s) to increment the current byte
            if filter_type == 1:  # Sub
                x += a
            elif filter_type == 2:  # Up
                x += b
            elif filter_type == 3:  # Average
                x += (a + b) // 2
            elif filter_type == 4:  # Paeth
                x += PaethPredictor(a, b, c)
            # Finally truncate to byte and append int to list
            recon_vals.append(x & 0xFF)
    recon_len = len(recon_vals)
    if recon_len != expected_len:
        raise ValueError(f"Reconstructed {recon_len} bytes but expected {expected_len}")
    return recon_vals


def PaethPredictor(a: int, b: int, c: int) -> int:  # pragma: no cover
    """
    See: http://www.libpng.org/pub/png/spec/1.2/PNG-Filters.html

    "A simple predictive-corrective coding filter" or P-C filter,
    described in Paeth (1991) "Image File Compression Made Easy".
    """
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        Pr = a
    elif pb <= pc:
        Pr = b
    else:
        Pr = c
    return Pr
