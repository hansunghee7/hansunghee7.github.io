import os
import sys
from json import (
    dumps,
    loads,
)
import re


def run(argv):
    parsed = re.compile("a").match(argv[0])
    count = len(argv)
    return dumps(argv)


if __name__ == "__main__":
    print(run(sys.argv), os.sep)
