from setuptools import setup, find_packages

# Read long description from README and CHANGELOG
def read_long_description():
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            readme = f.read()
        with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
            changelog = f.read()
        return readme + '\n\n## Changelog\n\n' + changelog
    except FileNotFoundError:
        return open('README.md').read()

setup(
    name='jsonlite',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    packages=find_packages(),
    include_package_data=True,
    description='A lightweight local JSON database with MongoDB-compatible API',
    long_description=read_long_description(),
    long_description_content_type='text/markdown',
    author='simpx',
    author_email='simpxx@gmail.com',
    url='https://github.com/simpx/jsonlite',
    license='MIT',
    install_requires=[],
    extras_require={
        'performance': ['orjson>=3.0.0'],
        'security': ['cryptography>=3.0.0'],
        'dev': ['pytest>=6.0.0', 'pytest-cov>=2.0.0', 'setuptools_scm'],
    },
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Database',
        'Topic :: Database :: Database Engines/Servers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
    keywords='database json mongodb pymongo local embedded',
    test_suite='tests',
    project_urls={
        'Documentation': 'https://github.com/simpx/jsonlite#readme',
        'Source': 'https://github.com/simpx/jsonlite',
        'Tracker': 'https://github.com/simpx/jsonlite/issues',
        'Changelog': 'https://github.com/simpx/jsonlite/blob/main/CHANGELOG.md',
    },
)
