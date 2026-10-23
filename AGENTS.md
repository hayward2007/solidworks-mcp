# Repository work

- Preserve existing work and native CAD baselines. Native SolidWorks COM runs on Windows.
- Portable design CLI: `python -m solidworks_mcp`; installed entry point: `sw-design`.
- Install: `python -m pip install -e .`; Windows CAD/numerical extras: `-e '.[cad]'`.
- Read `docs/design-studio/README.md` for the workflow and `knowledge/product-design-policy.md`
  before mechanical product design. Default RAG mode is quality; do not impose old
  ten-line specs or suppress visual evidence to save tokens.
- Keep numerical inputs, units, references, conditions and uncertainty explicit.
- Never record human approval on the user's behalf. This restriction applies to
  product-design review records, not ordinary repository code fixes and tests.
- Use the existing dedicated gear/topology tools where applicable. Do not claim
  Windows CAD, physical tests, FEA or sensor validation from portable unit tests.
- Shared service logic belongs in `solidworks_mcp/design`; both MCP servers and the
  CLI use it. No provider API calls, hidden shell evaluation or automatic uploads.
- Tests: `python -m unittest solidworks_mcp.tests.test_design_studio solidworks_mcp.tests.test_setup solidworks_mcp.tests.test_gears solidworks_mcp.tests.test_topopt solidworks_mcp.tests.test_verification` (the last runs on Windows only). Started from the MCP server's `execute_python`, pass `stdin=subprocess.DEVNULL`: an inherited stdio pipe makes the CLI test hang.
- The wheel build copies `knowledge/` into packaged resources. Edit the source corpus,
  not a generated duplicate. Private artifacts/DB/reports belong in `.design-studio/`.
