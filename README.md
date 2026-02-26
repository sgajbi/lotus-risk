# lotus-risk

Lotus backend service

## Quick Start

`powershell
make install
make lint
make typecheck
make openapi-gate
make ci
`",
  ",
  

`powershell
uvicorn src.app.main:app --reload --port 8000
`",
  ",
  

- CI and governance: .github/workflows/
- Engineering commands: Makefile
- Platform standards docs: docs/standards/
