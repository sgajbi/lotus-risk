from src.app.main import app


def main() -> None:
    spec = app.openapi()
    if "paths" not in spec or not spec["paths"]:
        raise SystemExit("OpenAPI gate failed: no paths defined")
    print("OpenAPI gate passed")


if __name__ == "__main__":
    main()
