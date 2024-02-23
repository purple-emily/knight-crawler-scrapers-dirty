Write-Output "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
Write-Output "ONLY START ONE PRODUCER"
Write-Output "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"

# Run the script with Poetry
poetry run python -m src.scrapers.main producer $args
