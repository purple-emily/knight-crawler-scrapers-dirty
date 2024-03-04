lint:
	-poetry run ruff check src/scrapers
	-poetry run pyright src/scrapers
	-poetry run codespell src/scrapers

test:
	poetry run pytest
