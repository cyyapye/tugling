import argparse


def greeting(name):
    return f"Hello, {name}!"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="World")
    print(greeting(parser.parse_args().name))
