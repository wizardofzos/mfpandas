import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="mfpandas",
    version="0.0.1",
    author="Wizard of z/OS",
    author_email="wizard@zdevops.com",
    description="Parsing various z/OS structures into Panda dataframes.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wizardofzos/mfpandas",
    project_urls={
        "Bug Tracker": "https://github.com/wizardofzos/mfpandas/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    include_package_data=True,
    install_requires=[
        'wheel',
        'pandas>=1.5.2',
        'xlsxwriter>=3.1.0'
    ],
    python_requires=">=3.6",
)
