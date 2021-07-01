import requests
from pathlib import Path

url = "https://raw.githubusercontent.com/lmmx/range-streams/master/example_text_file.txt"

def get_bytes(bytes_range: str):
    r = requests.get(url, stream=True, headers={"range": f"bytes={bytes_range}"})
    return r

if __name__ == "__main__":
    bytes_range = "-0"
    r = get_bytes(bytes_range=bytes_range)
    print(f"No byte: {bytes_range=} --> {r.raw.read()=}")

    print()
    print(f'File length from response: {r.headers["Content-Range"].split("/")[-1]=}')
    print(f'File length from file: {len(Path("example_text_file.txt").read_bytes())=}')
    
    print()
    bytes_range = "0-0"
    r = get_bytes(bytes_range=bytes_range)
    print(f"First byte: {bytes_range=} --> {r.raw.read()=}")
    print()

    bytes_range = "0-1"
    r = get_bytes(bytes_range=bytes_range)
    print(f"First 2 bytes: {bytes_range=} --> {r.raw.read()=}")
    print()

    bytes_range = "-1"
    r = get_bytes(bytes_range=bytes_range)
    print(f"Last byte: {bytes_range=} --> {r.raw.read()=}")
