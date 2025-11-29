build:
	docker-compose build

up:
	docker-compose up

down:
	docker-compose down

restart:
	docker-compose down
	docker-compose build
	docker-compose up

migrate:
	docker-compose run --rm backend python manage.py migrate

makemigrations:
	docker-compose run --rm backend python manage.py makemigrations

shell:
	docker-compose run --rm backend python manage.py shell

deploy-docker:
	git pull
	make build
	make up -d

lint:
	ruff check .
	black --check .

test:
	python manage.py test
