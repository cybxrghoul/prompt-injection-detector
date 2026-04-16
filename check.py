import os
if not os.path.exists("data"):
    os.makedirs("data")
with open("data/testfile.txt", "w") as f:
    f.write("hello world\n")
