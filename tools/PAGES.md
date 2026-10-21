# Publishing coverage within the Pages size limit

`pages.yml` stages a site in the runner's temporary directory with
`python3 tools/stage-pages.py --revision "$REPORT_REVISION" --output "$PAGES_DIRECTORY"`.
The revision must be the full report-repository commit SHA being published.
The output must be a new directory outside the checkout. Staging never removes
or rewrites report files in the checkout.

The published site contains:

- The existing dashboard, CSV/JSON exports, historical metrics, and slangc trend.
- Eight current source-browsing views: full and slangc for Linux, macOS, Windows,
  and the cross-platform merged report. These use the newer LCOV HTML renderer.
- Existing platform entry URLs, which redirect to the corresponding current view.
- Historical report entry pages that explain how to retrieve the original report
  from a pinned Git revision. Historical summary JSON remains published.

The site excludes duplicate native-renderer HTML, historical source HTML, stale
legacy files under `latest`, and raw LCOV/text inputs. Those remain in Git, subject
to the repository's existing cleanup policy. This staging change does not change
that policy or delete production history. Some older snapshots already contain
only summary data. Per-file deep links into excluded native
or historical HTML are no longer served by Pages. The archive notices preserve
report entry navigation, rather than silently substituting today's coverage for
an old report.

The Linux/macOS LCOV views are not a lossless replacement for native llvm-cov
region annotations. Their summary totals use the existing authoritative summary
inputs, but native annotations remain available in the original report files.
To inspect an archived or native report, clone this repository, check out the
revision linked from the site, and open its `index.html` locally. GitHub's source
viewer does not render the report HTML as a website.

Staging requires Linux/macOS and merged full/slangc report indexes. Windows
views are required when the combined summary contains a Windows result; an
empty Windows result produces an explicit unavailable notice instead. Every run
records the content size and tar bound in the Actions job summary. Content at or above 800,000,000
bytes emits an early GitHub warning. It fails if content exceeds
950,000,000 bytes or a conservative tar size bound reaches 1,000,000,000 bytes.
This leaves room for tar metadata under the
[1 GB published-site limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).
A future size failure needs an explicit publishing decision; the script never
drops a current view to fit the budget. Input symlinks and special files are
rejected, and output copies are regular files, so deduplication cannot introduce
Pages-incompatible hard links.

Run the fixture tests with:

```console
python3 -m unittest discover -s tools/tests -v
```

For a publication check, stage the current report checkout, inspect the reported
size, verify navigation and source links, then upload only the staged directory.
A successful local build does not verify GitHub's deployment acceptance or the
served site. After an authorized rollout, check the Pages run, dashboard date,
all platform and merged views, history notices, exports, and trend page. The next
nightly should also publish successfully with the same staging policy.

The staged site also includes `reports/publication.json`, identifying the report
repository commit being published. The source nightly's publication checker
requires both a successful Pages run for its pushed commit and this exact marker
on the public site. Deploy this staging/marker change before enabling that
source-side check. The checker uses public read-only endpoints, has a bounded
wait, and makes deployment failures or stale content fail the source nightly.
Existing workflow failure notifications can then report the publication problem.
This does not require new credentials or change report retention.
