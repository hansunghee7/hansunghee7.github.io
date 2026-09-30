from os.path import (
    basename,
    dirname,
    join,
)
import sys


def name(p):
    return basename(p) + join(p, "x")


if __name__ == "__main__":
    print(name(sys.argv[0]))
