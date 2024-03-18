
rabbit:
	docker run --rm -d --hostname the-rabbit --name the-rabbit -p 5672:5672 rabbitmq:3


stub:
	poetry run pyright --createstub $(filter-out $@,$(MAKECMDGOALS))


lint:
	poetry run codespell src/scrapers
	poetry run ruff check src/scrapers
	poetry run pyright src/scrapers

test:
	poetry run pytest
