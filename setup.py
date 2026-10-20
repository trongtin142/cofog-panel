from setuptools import setup, find_packages

# Read version from __init__.py
with open("cofog_panel/__init__.py") as f:
    version = next(line for line in f if line.startswith('__version__')).split('=')[1].strip().strip('"\'')

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cofog-panel",
    version=version,
    author="Trong Tin Nguyen",
    author_email="nttin@hcmiu.edu.vn",
    description="Tool to harmonize IMF GFS COFOG data into reproducible panel datasets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/royalgarter/cofog-panel",
    packages=find_packages(exclude=("tests",)), # Ensure only directories with __init__.py are included
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl>=3.1.5",
        "typer>=0.9.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0"],
        "replication": ["statsmodels>=0.14", "matplotlib>=3.9"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires='>=3.10',
    
    # DEFINE ENTRY POINT FOR CLI
    entry_points={
        'console_scripts': [
            'cofog-panel = cofog_panel.cli:app', 
        ],
    },
)