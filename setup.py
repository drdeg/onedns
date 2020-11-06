import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    requires = fh.read().splitlines()

setuptools.setup(
    name="onedns-drdeg", # Replace with your own username
    version="0.0.1",
    author="David Degerfeldt",
    author_email="david@degerfeldt.se",
    description="A package for updating DNS A-records at one.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/drdeg/onedns",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPLv3",
        "Operating System :: OS Independent",
    ],
    install_requires=requires
)