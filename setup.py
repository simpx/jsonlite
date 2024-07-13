from setuptools import setup, find_packages

setup(
    name='jsonlite',
    version='0.0.5',
    packages=find_packages(),
    include_package_data=True,
    description='A lightweight local JSON database',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='simpx',
    author_email='simpxx@gmail.com',
    url='',
    license='MIT',
    install_requires=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    test_suite='tests',
)