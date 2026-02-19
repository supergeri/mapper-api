import json
import argparse
import sys

from backend.adapters.ingest_to_cir import to_cir
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.core.canonicalize import canonicalize


def main():
    parser = argparse.ArgumentParser(description="Convert workout files to Garmin YAML format")
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("-o", "--output", help="Output YAML file path (default: stdout)")

    args = parser.parse_args()

    try:
        # Load input JSON
        with open(args.input, 'r') as f:
            ingest_data = json.load(f)

        # Convert to CIR format
        cir = to_cir(ingest_data)

        # Canonicalize exercise names
        cir = canonicalize(cir)

        # Convert to Garmin YAML
        garmin_yaml = to_garmin_yaml(cir)

        # Output result
        if args.output:
            with open(args.output, 'w') as f:
                f.write(garmin_yaml)
        else:
            print(garmin_yaml)

    except FileNotFoundError:
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
