from stream_response import ResponseStream
import requests

url = "https://raw.githubusercontent.com/lmmx/range-streams/master/example_text_file.txt"
url2 = "https://httpbin.org/stream/20"

with open("example_text_file.txt", "rb") as f:
  b = f.read()

import io
from io import SEEK_SET, SEEK_END
i = io.BytesIO(b)
i.seek(0, SEEK_END)
endpos = i.tell()
print(f"{endpos=}")

i.seek(-4, 2)
print(i.read(2))

r = requests.get(url, stream=True)
it = r.iter_content(chunk_size=4)
s = ResponseStream(it)
print(s.read(2))
s.seek(-3, 2)
print(s.read(2))

r = requests.get(url, stream=True)
it = r.iter_content(chunk_size=4)
s = ResponseStream(it)
s.seek(0,2)
print(s.tell())

r = requests.get(url, stream=True)
it = r.iter_content(chunk_size=4)
s = ResponseStream(it)
s.seek(-4,2)
print(s.read(2))
