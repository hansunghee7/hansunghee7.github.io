import json
import sys
import json


def dump(x):
    return json.dumps(x)


if __name__ == "__main__":
    print(dump(sys.argv))
