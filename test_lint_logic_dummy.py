import json
import os
import sys


def total(items):
    unused_count = len(items)
    result = 0
    for item in items:
        result += item
    return result


def main():
    print(total([1, 2, 3]), sys.argv)


if __name__ == "__main__":
    main()
