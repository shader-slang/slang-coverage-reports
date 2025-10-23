# Slang Coverage Reports

Historical code coverage reports for the [Slang shader compiler](https://github.com/shader-slang/slang).

## Latest Coverage

🔗 **[View Latest Coverage Report](https://shader-slang.github.io/slang-coverage-reports/reports/latest/)**

## Historical Reports

📊 **[Browse Historical Reports](https://shader-slang.github.io/slang-coverage-reports/reports/history/)**

---

**📅 Updated:** Nightly at 2 AM UTC
**🔄 Source:** [Coverage Workflow](https://github.com/shader-slang/slang/blob/master/.github/workflows/coverage-nightly.yml)
**🛠️ Tool:** LLVM Coverage (llvm-cov)

## About

This repository stores code coverage reports generated from the main Slang repository. Coverage is measured by running the full test suite with instrumentation enabled.

- **Latest report:** Always at `reports/latest/`
- **Historical reports:** Organized by date and commit in `reports/history/YYYY-MM-DD-commit/`

## Repository Pattern

This repository follows the same pattern as [slang-material-modules-benchmark](https://github.com/shader-slang/slang-material-modules-benchmark):
- Automated updates from main repository CI
- Historical data accumulation
- GitHub Pages deployment for visualization
- Minimal maintenance required
