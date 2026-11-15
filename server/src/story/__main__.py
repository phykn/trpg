import argparse
import sys

from .check import report_checks

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check one story folder without starting the server.")
    parser.add_argument("folder")
    sys.exit(report_checks(parser.parse_args().folder))
