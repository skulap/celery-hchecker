import os
from setuptools import setup, find_packages

# Чтение README с указанием кодировки
with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='celery-hchecker',
    version='0.0.2',
    packages=find_packages(where="src"),
    include_package_data=True,
    long_description_content_type="text/markdown",
    long_description=long_description,
    package_dir={"": "src"},
    install_requires=[
        'kombu>=5.0',
        'cachetools>=6.0',
        'celery>=5.1',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    python_requires='>=3.10',
)
