import sys
from importlib import resources
from pathlib import Path
from .. import files
import pkg_resources


def check_requirements():
    
    requirements_file: Path = resources.files(files) / "requirements.txt"
    with requirements_file.open("r", encoding='utf-8') as f:
        required_packages = [
            line.rstrip() for line in f
        ]

    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}

    missing_packages = []
    for required_package in required_packages:
        if not required_package:  # Skip empty lines
            continue
        pkg = pkg_resources.Requirement.parse(required_package)
        if (
            pkg.key not in installed_packages
            or pkg_resources.parse_version(installed_packages[pkg.key])
            not in pkg.specifier
        ):
            missing_packages.append(str(pkg))

    if missing_packages:
        print("Missing packages:")
        print(", ".join(missing_packages))
        return True
    return False
