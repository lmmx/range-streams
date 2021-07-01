import requests

url = "https://raw.githubusercontent.com/lmmx/range-streams/master/example_text_file.txt"

def get_bytes(bytes_range: str):
    r = requests.get(url, stream=True, headers={"range": f"bytes={bytes_range}"})
    return r

if __name__ == "__main__":
    r = get_bytes(bytes_range="0-0")
    print(f"First byte: {r.raw.read()=}")
    r = get_bytes(bytes_range="0-1")
    print(f"First 2 bytes: {r.raw.read()=}")
