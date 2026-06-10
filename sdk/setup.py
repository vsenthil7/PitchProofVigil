from setuptools import find_packages, setup

setup(
    name="pitchproof-vigil-sdk",
    version="0.1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=["httpx>=0.27"],
    entry_points={"console_scripts": ["ppv=pitchproof_vigil.cli:main"]},
    python_requires=">=3.10",
)
