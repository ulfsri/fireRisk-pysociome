
from setuptools import setup, find_packages

setup(
    name="pysociome",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "scikit-learn",
        "requests",
    ],
    author="Hossein Lotfi",
    author_email="hlotfi@ulri.org",
    description="Operationalizing Social Determinants of Health Data in Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/ulfsri/fireRisk-pysociome",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
