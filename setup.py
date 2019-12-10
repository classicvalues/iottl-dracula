from setuptools import setup, find_packages


with open("requirements.txt") as f:
    requirements = f.read().splitlines()


setup(
    name = "iottl",
    version = "0.1.0",
    install_requires=requirements,
    author = "Martin Hron",
    author_email = "hron@avast.com",
    description = ("IoT Threats Lab SDK"),
    packages = find_packages(),
)
