from range_stream import ResponseStream
import httpx

test_url = (
        "https://raw.githubusercontent.com/lmmx/range-streams/"
        "bb5e0cc2e6980ea9e716a569ab0322587d3aa785/example_text_file.txt"
    )

def main(url: str):
    response = httpx.get(url)
    h = response.headers
    if "Accept-Ranges" not in h or h["Accept-Ranges"] != "bytes":
        raise ValueError("Not a range request capable server")
    stream = ResponseStream(response.iter_content())
    return stream.read(50)

if __name__ == "__main__":
    print(f"{test_url=}")
    main(url=test_url)
