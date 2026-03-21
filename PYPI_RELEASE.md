# PyPI Release Checklist

## Pre-Release Preparation

- [x] All tests passing (221 tests)
- [x] Documentation complete (API_REFERENCE.md, MIGRATION_GUIDE.md, TRANSACTIONS.md)
- [x] Examples added (basic_usage.py, advanced_features.py)
- [x] CHANGELOG.md updated
- [x] README.md updated with features and quick start
- [x] setup.py configured with metadata and extras_require
- [x] CI/CD pipeline created (.github/workflows/ci-cd.yml)

## Release Steps

### 1. Version Tag
```bash
# Ensure you're on main branch
git checkout main

# Create annotated tag for release
git tag -a v1.0.0 -m "Release v1.0.0 - Stable release with full MongoDB compatibility"

# Push tag to GitHub
git push origin v1.0.0
```

### 2. GitHub Release
1. Go to https://github.com/simpx/jsonlite/releases
2. Click "Draft a new release"
3. Select tag v1.0.0
4. Copy changelog from CHANGELOG.md (Unreleased section)
5. Publish release

### 3. Automatic PyPI Publish
- CI/CD pipeline will automatically:
  - Run tests on Python 3.6-3.12
  - Run linting checks
  - Build package (sdist + wheel)
  - Upload to PyPI

### 4. Verify Release
```bash
# Wait a few minutes for PyPI to process
pip install --upgrade jsonlite
python -c "import jsonlite; print(jsonlite.__version__)"
```

## Post-Release

- [ ] Update ROADMAP.md with release date
- [ ] Announce release on social media / forums
- [ ] Update project website (if applicable)
- [ ] Monitor PyPI downloads and issues

## Manual Publish (Fallback)

If automatic publish fails:

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Test upload to TestPyPI first
twine upload --repository testpypi dist/*

# Verify on TestPyPI
pip install --index-url https://test.pypi.org/simple/ jsonlite

# Upload to production PyPI
twine upload dist/*
```

## Secrets Required

GitHub repository secrets needed for automatic publish:
- `PYPI_API_TOKEN` - PyPI API token with upload permissions

Generate token at: https://pypi.org/manage/account/token/

---

**Release Date**: TBD
**Version**: 1.0.0
**Status**: Ready for Release
