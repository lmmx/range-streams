import requests
from io import BytesIO, SEEK_SET, SEEK_END

class ResponseStream:
    def __init__(self, request_iterator):
        self._bytes = BytesIO()
        self._iterator = request_iterator

    def _load_all(self):
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self):
        return self._bytes.tell()

    def read(self, size=None):
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)
    
    def seek(self, position, whence=SEEK_SET):
        if whence == SEEK_END:
            self._load_all()
        self._bytes.seek(position, whence)

def main(url: str):
    response = requests.get(url, stream=True)
    h = response.headers
    if "Content-Length" in h or "Transfer-Encoding" not in h or h["Transfer-Encoding"] != "chunked":
        raise ValueError("Not a chunked stream")
    stream = ResponseStream(response.iter_content(chunk_size=64))
    # Read the first 50 bytes of the file without loading the rest of it
    return stream.read(50)

if __name__ == "__main__":
    url = "https://httpbin.org/stream/20"
    print(f"{url=}")
    b = main(url=url)
    print(b)
    print()
    url = "https://raw.githubusercontent.com/lmmx/range-streams/master/example_text_file.txt"
    print(f"{url=}")
    main(url=url)
