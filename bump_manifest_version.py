import argparse
import logging
import os
import re

_logger = logging.getLogger(__name__)

SEARCH_ROOT = os.path.dirname(os.path.abspath(__file__))

MANIFEST_FILENAME = "__manifest__.py"
VERSION_PATTERN = re.compile(r"(\"version\"\s*:\s*\")([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)(\")")


def bump_version(version_str):
    parts = version_str.split(".")
    if len(parts) != 4:
        return version_str  # Unexpected format
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def replace_major_version(version_str, target_major):
    parts = version_str.split(".")
    if len(parts) != 4:
        return version_str  # Unexpected format
    parts[0] = str(target_major)
    return ".".join(parts)


def process_manifest(path, target_major=None):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    match = VERSION_PATTERN.search(content)
    if not match:
        return False
    old_version = match.group(2)
    if target_major is None:
        new_version = bump_version(old_version)
    else:
        new_version = replace_major_version(old_version, target_major)
    new_content = VERSION_PATTERN.sub(r'"version": "' + new_version + '"', content, count=1)
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        _logger.info(f"Updated {path}: {old_version} -> {new_version}")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Bump manifest version patch number or set major version.")
    parser.add_argument(
        "-v",
        "--version-major",
        type=int,
        help="Set major version (e.g. -v 19 updates 18.0.2.21 to 19.0.2.21).",
    )
    args = parser.parse_args()

    updated = 0
    for root, _dirs, files in os.walk(SEARCH_ROOT):
        for fname in files:
            if fname == MANIFEST_FILENAME:
                manifest_path = os.path.join(root, fname)
                if process_manifest(manifest_path, target_major=args.version_major):
                    updated += 1
    _logger.info(f"Done. {updated} manifest(s) updated.")


if __name__ == "__main__":
    main()
