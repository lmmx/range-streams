# Byte for the letter P at the start and K at the end
# Bytes counting from zero to eight in between
b = b"\x50\x00\x01\x02\x03\x04\x05\x06\x07\x08\x4b"

with open("../example_text_file.txt", "wb") as f:
    f.write(b)
