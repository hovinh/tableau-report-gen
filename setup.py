from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="tableau-report-gen",
    version="0.1.1",
    author="Vinh, Thong",
    author_email="hovinh39@gmail.com,ndthong2411@gmail.com",
    description="A tool to generate reports from Tableau workbooks.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ndthong2411/tableau-report-gen/tree/dev",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',
    install_requires=[
        "streamlit",
        "pandas",
        "logzero",
        "networkx",
        "graphviz",
        "tableauhyperapi",
        "xhtml2pdf"

    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'trggo=tableau_report_gen.launcher:main',  # Allows users to run the app via CLI
        ],
    },
)
